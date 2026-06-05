"""Integration tests for account auth (signup / login / token scoping).

Runs against a throwaway SQLite database via TestClient — the dialect-aware
type layer means the same models/queries exercise here as on Postgres.
"""
import os
import uuid

import pytest

# Configure a temp SQLite DB + dev providers BEFORE importing the app.
os.environ["ENVIRONMENT"] = "local"
os.environ["EMBEDDING_PROVIDER"] = "deterministic"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
_DB_PATH = os.path.join(os.path.dirname(__file__), "_auth_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.core.security import hash_password, verify_password  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _setup():
    if os.path.exists(_DB_PATH):
        os.remove(_DB_PATH)
    init_db()
    yield
    # Dispose the engine so Windows releases the file handle before cleanup.
    from app.core.database import get_engine

    get_engine().dispose()
    if os.path.exists(_DB_PATH):
        try:
            os.remove(_DB_PATH)
        except PermissionError:
            pass  # harmless leftover; gitignored


@pytest.fixture
def client():
    return TestClient(app)


def _email() -> str:
    return f"user{uuid.uuid4().hex[:8]}@example.com"


# ── Password primitive ───────────────────────────────────────────────────────

def test_password_hash_roundtrip_and_uniqueness():
    h1 = hash_password("s3cret-pass")
    h2 = hash_password("s3cret-pass")
    assert h1 != h2                       # random salt → different hashes
    assert h1.startswith("scrypt$")
    assert verify_password("s3cret-pass", h1)
    assert verify_password("s3cret-pass", h2)
    assert not verify_password("wrong", h1)


def test_verify_password_handles_garbage():
    assert verify_password("x", "not-a-valid-hash") is False
    assert verify_password("x", "") is False


# ── Signup ───────────────────────────────────────────────────────────────────

def test_signup_creates_account_and_returns_token(client):
    r = client.post("/api/auth/signup", json={
        "email": _email(), "full_name": "Test User", "password": "password123"
    })
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"]
    assert "password" not in body and "password_hash" not in body  # never leaked


def test_signup_rejects_short_password(client):
    r = client.post("/api/auth/signup", json={
        "email": _email(), "full_name": "T", "password": "short"
    })
    assert r.status_code == 422  # min_length=8


def test_signup_duplicate_email_conflicts(client):
    email = _email()
    first = client.post("/api/auth/signup", json={"email": email, "full_name": "A", "password": "password123"})
    assert first.status_code == 201
    dupe = client.post("/api/auth/signup", json={"email": email, "full_name": "A2", "password": "password123"})
    assert dupe.status_code == 409


# ── Login ────────────────────────────────────────────────────────────────────

def test_login_succeeds_with_correct_password(client):
    email = _email()
    client.post("/api/auth/signup", json={"email": email, "full_name": "Login User", "password": "password123"})
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_fails_with_wrong_password(client):
    email = _email()
    client.post("/api/auth/signup", json={"email": email, "full_name": "X", "password": "password123"})
    r = client.post("/api/auth/login", json={"email": email, "password": "WRONGpassword"})
    assert r.status_code == 401


def test_login_fails_for_unknown_email(client):
    r = client.post("/api/auth/login", json={"email": _email(), "password": "password123"})
    assert r.status_code == 401


# ── Token scoping (/me) ──────────────────────────────────────────────────────

def test_token_authorizes_me_endpoint(client):
    email = _email()
    tok = client.post("/api/auth/signup", json={"email": email, "full_name": "Me User", "password": "password123"}).json()["access_token"]
    r = client.get("/api/candidates/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["email"] == email


def test_me_rejected_without_token(client):
    assert client.get("/api/candidates/me").status_code == 401


def test_login_rotates_token_invalidating_old_one(client):
    email = _email()
    old = client.post("/api/auth/signup", json={"email": email, "full_name": "Rot", "password": "password123"}).json()["access_token"]
    new = client.post("/api/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
    assert old != new
    # old token no longer valid; new one is
    assert client.get("/api/candidates/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401
    assert client.get("/api/candidates/me", headers={"Authorization": f"Bearer {new}"}).status_code == 200


# ── Backward compatibility: guest flow still works ───────────────────────────

def test_guest_registration_still_works(client):
    r = client.post("/api/candidates", json={"email": _email(), "full_name": "Guest"})
    assert r.status_code == 201
    assert r.json()["access_token"]


def test_guest_account_can_be_claimed_via_signup(client):
    email = _email()
    # guest first (no password)
    client.post("/api/candidates", json={"email": email, "full_name": "Guest"})
    # then claim with a password
    r = client.post("/api/auth/signup", json={"email": email, "full_name": "Now Real", "password": "password123"})
    assert r.status_code == 201
    # and can log in afterwards
    assert client.post("/api/auth/login", json={"email": email, "password": "password123"}).status_code == 200
