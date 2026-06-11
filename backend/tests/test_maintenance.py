"""Integration tests for the scheduled-maintenance endpoints (X-API-Key gated)."""
import os
import uuid

import pytest

os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("EMBEDDING_PROVIDER", "deterministic")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
_DB_PATH = os.path.join(os.path.dirname(__file__), f"_maint_test_{uuid.uuid4().hex[:6]}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402

KEY = {"X-API-Key": get_settings().SCRAPER_API_KEY}


@pytest.fixture(scope="module", autouse=True)
def _setup():
    if os.path.exists(_DB_PATH):
        os.remove(_DB_PATH)
    init_db()
    yield
    from app.core.database import get_engine

    get_engine().dispose()
    if os.path.exists(_DB_PATH):
        try:
            os.remove(_DB_PATH)
        except PermissionError:
            pass


@pytest.fixture
def client():
    return TestClient(app)


def test_stale_requires_api_key(client):
    assert client.post("/api/maintenance/stale").status_code in (401, 422)
    assert client.post("/api/maintenance/stale", headers={"X-API-Key": "wrong"}).status_code == 401


def test_stale_runs_and_reports(client):
    r = client.post("/api/maintenance/stale?days=30", headers=KEY)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert "deactivated" in body


def test_alerts_runs_for_each_frequency(client):
    for freq in ("daily", "weekly"):
        r = client.post(f"/api/maintenance/alerts?frequency={freq}", headers=KEY)
        assert r.status_code == 200
        assert r.json()["status"] == "success"


def test_ingest_status_gated_and_idle(client):
    assert client.get("/api/ingest/status").status_code in (401, 422)
    r = client.get("/api/ingest/status", headers=KEY)
    assert r.status_code == 200
    assert "state" in r.json()
