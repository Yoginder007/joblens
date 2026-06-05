"""
Security primitives.

Three boundaries:
  1. Scraper / server-to-server auth via the ``X-API-Key`` header.
  2. Per-candidate bearer tokens so résumé PII endpoints are owner-scoped.
     Tokens are generated once and stored only as a SHA-256 hash — the raw
     token is returned to the client a single time.
  3. Account passwords, hashed with ``scrypt`` (a memory-hard KDF from the
     standard library) using a per-user random salt. No third-party deps,
     which keeps the image small enough for the free hosting tier.
"""
import hashlib
import hmac
import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return secrets.compare_digest(hash_token(token), token_hash)


# ── Password hashing (scrypt, stdlib) ────────────────────────────────────────
# Format stored in the DB: "scrypt$<n>$<r>$<p>$<salt_hex>$<dk_hex>" — self-
# describing so parameters can evolve without a data migration.
_SCRYPT_N = 2**14  # CPU/memory cost (16384) — solid for an interactive login
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_DKLEN,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verify against a stored ``scrypt$…`` string."""
    try:
        scheme, n, r, p, salt_hex, dk_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(dk_hex)),
        )
        return hmac.compare_digest(dk, bytes.fromhex(dk_hex))
    except (ValueError, AttributeError):
        return False


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
