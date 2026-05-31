"""
Security primitives.

Two boundaries:
  1. Scraper / server-to-server auth via the ``X-API-Key`` header.
  2. Per-candidate bearer tokens so résumé PII endpoints are owner-scoped.
     Tokens are generated once at candidate creation and stored only as a
     SHA-256 hash — the raw token is returned to the client a single time.
"""
import hashlib
import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return secrets.compare_digest(hash_token(token), token_hash)


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """Validate the scraper API key in constant time."""
    settings = get_settings()
    if not secrets.compare_digest(x_api_key, settings.SCRAPER_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )
    return x_api_key


def extract_bearer_token(authorization: str | None) -> str:
    """Pull the raw token out of an ``Authorization: Bearer <token>`` header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    return authorization[7:].strip()
