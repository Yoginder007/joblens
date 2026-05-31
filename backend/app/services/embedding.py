"""
Embedding service with a pluggable provider.

  - "sentence-transformers": lazy-loaded, thread-safe real model.
  - "deterministic": stable hash-seeded vectors for tests/CI (no model download).

Determinism note: we seed from a SHA-256 digest, NOT Python's built-in hash(),
which is randomised per-process. The same text therefore yields the same vector
across restarts.
"""
import hashlib
import logging
import threading

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)

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


def embed_text(text: str) -> list[float]:
    settings = get_settings()
    text = (text or "").strip() or "general"

    if settings.EMBEDDING_PROVIDER == "deterministic":
        rng = np.random.RandomState(_stable_seed(text))
        vec = rng.randn(settings.EMBEDDING_DIMENSION).astype(np.float32)
    else:
        vec = np.asarray(
            _get_model().encode(text[:2000], show_progress_bar=False), dtype=np.float32
        )

    norm = float(np.linalg.norm(vec))
    if norm > 1e-8:
        vec = vec / norm
    return vec.tolist()


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
    return embed_text(" ".join(parts))


def embed_job(title: str, description: str = "", skills: list[str] | None = None) -> list[float]:
    parts = [title]
    if description:
        parts.append(description[:500])
    if skills:
        parts.extend(skills)
    return embed_text(" ".join(parts))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom < 1e-8:
        return 0.0
    return float(np.dot(va, vb) / denom)
