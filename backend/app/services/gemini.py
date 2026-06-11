"""
Minimal Gemini REST client shared by the embedding and parsing services.

Plain httpx against the generativelanguage API — no SDK, which keeps the
production image small enough for the 512 MB free tier. The API key travels in
a header (never the URL) so it can't leak into exception messages or logs.
"""
import logging
import time

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

BASE = "https://generativelanguage.googleapis.com/v1beta"
_RETRYABLE = {429, 500, 502, 503, 504}


def gemini_post(path: str, payload: dict) -> dict:
    """Single HTTP call — kept as a thin seam so tests can mock it."""
    settings = get_settings()
    resp = httpx.post(
        f"{BASE}/{path}",
        json=payload,
        headers={"x-goog-api-key": settings.GOOGLE_API_KEY},
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()


def gemini_call(path: str, payload: dict, attempts: int = 4) -> dict:
    """Call with exponential backoff on rate limits / transient errors.

    Raises on persistent failure; callers decide their own fallback policy
    (embeddings must NOT fall back silently, parsing may fall back to regex).
    """
    delay = 2.0
    for attempt in range(attempts):
        try:
            return gemini_post(path, payload)
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
