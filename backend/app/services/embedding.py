"""
Embedding service with a pluggable provider.

  - "gemini": real semantic vectors from the Gemini API (``gemini-embedding-001``)
    over plain REST (httpx) — no SDK, no torch, fits the 512 MB hosting tier.
    Output is MRL-truncated to ``EMBEDDING_DIMENSION`` and re-normalised
    client-side (truncated Gemini vectors are not unit-length), so the
    pgvector schema is identical across providers.
  - "sentence-transformers": lazy-loaded, thread-safe local model.
  - "deterministic": stable hash-seeded vectors for tests/CI (no model
    download, no network).

Task types: résumés embed as RETRIEVAL_QUERY and jobs as RETRIEVAL_DOCUMENT —
the asymmetric pairing these models are trained on for query→corpus retrieval.

Determinism note: the deterministic provider seeds from a SHA-256 digest, NOT
Python's built-in hash(), which is randomised per-process. The same text
therefore yields the same vector across restarts.
"""
import hashlib
import logging
import threading
import time

import httpx
import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)

TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
# batchEmbedContents accepts up to 100 items; 50 keeps each call comfortably
# inside the free-tier tokens-per-minute budget.
GEMINI_BATCH_SIZE = 50
_RETRYABLE = {429, 500, 502, 503, 504}
_MAX_CHARS = 2000

_lock = threading.Lock()
_model = None


def _stable_seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**31)


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                settings = get_settings()
                logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
                _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm > 1e-8:
        vec = vec / norm
    return vec


# ── Gemini REST client ───────────────────────────────────────────────────────

def _gemini_post(path: str, payload: dict) -> dict:
    """Single HTTP call — kept as a thin seam so tests can mock it.

    The key travels in a header (never the URL) so it can't leak into
    exception messages or access logs.
    """
    settings = get_settings()
    resp = httpx.post(
        f"{_GEMINI_BASE}/{path}",
        json=payload,
        headers={"x-goog-api-key": settings.GOOGLE_API_KEY},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def _gemini_call(path: str, payload: dict, attempts: int = 4) -> dict:
    """Call with exponential backoff on rate limits / transient errors.

    Raises on persistent failure — we never silently fall back to the
    deterministic provider, which would poison the vector space with
    incompatible embeddings.
    """
    delay = 2.0
    for attempt in range(attempts):
        try:
            return _gemini_post(path, payload)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status not in _RETRYABLE or attempt == attempts - 1:
                raise
            logger.warning("Gemini HTTP %s — retry %d in %.0fs", status, attempt + 1, delay)
        except httpx.HTTPError as exc:
            if attempt == attempts - 1:
                raise
            logger.warning("Gemini transport error (%s) — retry %d in %.0fs", exc, attempt + 1, delay)
        time.sleep(delay)
        delay *= 3
    raise RuntimeError("unreachable")  # pragma: no cover


def _gemini_request_body(text: str, task: str, settings) -> dict:
    return {
        "model": f"models/{settings.GEMINI_EMBEDDING_MODEL}",
        "content": {"parts": [{"text": text}]},
        "taskType": task,
        "outputDimensionality": settings.EMBEDDING_DIMENSION,
    }


def _clean(text: str) -> str:
    return ((text or "").strip() or "general")[:_MAX_CHARS]


# ── Public API ───────────────────────────────────────────────────────────────

def embed_text(text: str, task: str = TASK_DOCUMENT) -> list[float]:
    settings = get_settings()
    text = _clean(text)

    if settings.EMBEDDING_PROVIDER == "deterministic":
        rng = np.random.RandomState(_stable_seed(text))
        vec = rng.randn(settings.EMBEDDING_DIMENSION).astype(np.float32)
    elif settings.EMBEDDING_PROVIDER == "gemini":
        data = _gemini_call(
            f"models/{settings.GEMINI_EMBEDDING_MODEL}:embedContent",
            _gemini_request_body(text, task, settings),
        )
        vec = np.asarray(data["embedding"]["values"], dtype=np.float32)
    else:
        vec = np.asarray(
            _get_model().encode(text, show_progress_bar=False), dtype=np.float32
        )

    return _normalize(vec).tolist()


def embed_texts(texts: list[str], task: str = TASK_DOCUMENT) -> list[list[float]]:
    """Batch embedding. On Gemini this uses ``batchEmbedContents`` (one HTTP
    call per ``GEMINI_BATCH_SIZE`` texts); other providers map over
    ``embed_text``. Order is preserved."""
    settings = get_settings()
    if settings.EMBEDDING_PROVIDER != "gemini":
        return [embed_text(t, task) for t in texts]

    out: list[list[float]] = []
    for i in range(0, len(texts), GEMINI_BATCH_SIZE):
        chunk = texts[i:i + GEMINI_BATCH_SIZE]
        data = _gemini_call(
            f"models/{settings.GEMINI_EMBEDDING_MODEL}:batchEmbedContents",
            {"requests": [_gemini_request_body(_clean(t), task, settings) for t in chunk]},
        )
        for emb in data["embeddings"]:
            out.append(_normalize(np.asarray(emb["values"], dtype=np.float32)).tolist())
    return out


def embed_resume(parsed_data: dict) -> list[float]:
    parts: list[str] = []
    if parsed_data.get("current_title"):
        parts.append(parsed_data["current_title"])
    for cat in parsed_data.get("technical_skills", []) or []:
        if isinstance(cat, dict):
            parts.extend(cat.get("skills", []))
        elif isinstance(cat, str):
            parts.append(cat)
    parts.extend(parsed_data.get("domain_expertise", []) or [])
    # The résumé is the query side of the retrieval pair.
    return embed_text(" ".join(parts), task=TASK_QUERY)


def job_embedding_text(title: str, description: str = "", skills: list[str] | None = None) -> str:
    parts = [title]
    if description:
        parts.append(description[:500])
    if skills:
        parts.extend(skills)
    return " ".join(parts)


def embed_job(title: str, description: str = "", skills: list[str] | None = None) -> list[float]:
    return embed_text(job_embedding_text(title, description, skills), task=TASK_DOCUMENT)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom < 1e-8:
        return 0.0
    return float(np.dot(va, vb) / denom)
