"""Unit tests for the Gemini embedding provider (HTTP mocked — no network)."""
import os

import httpx
import numpy as np
import pytest

os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("EMBEDDING_PROVIDER", "deterministic")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

from app.core.config import Settings, get_settings  # noqa: E402
from app.services import embedding  # noqa: E402


@pytest.fixture
def gemini_settings(monkeypatch):
    """Force the gemini provider with a fake key for the duration of a test."""
    settings = get_settings().model_copy(
        update={"EMBEDDING_PROVIDER": "gemini", "GOOGLE_API_KEY": "test-key"}
    )
    monkeypatch.setattr(embedding, "get_settings", lambda: settings)
    return settings


def _fake_vector(dim: int, seed: float = 0.5) -> list[float]:
    # Deliberately NOT unit-length: verifies client-side normalisation.
    return [seed] * dim


# ── Config guard ─────────────────────────────────────────────────────────────

def test_gemini_provider_requires_api_key():
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        Settings(EMBEDDING_PROVIDER="gemini", GOOGLE_API_KEY="", _env_file=None)


def test_gemini_provider_accepts_key():
    s = Settings(EMBEDDING_PROVIDER="gemini", GOOGLE_API_KEY="abc", _env_file=None)
    assert s.GEMINI_EMBEDDING_MODEL == "gemini-embedding-001"


# ── Single embed ─────────────────────────────────────────────────────────────

def test_embed_text_gemini_returns_normalized_vector(gemini_settings, monkeypatch):
    captured: dict = {}

    def fake_post(path, payload):
        captured["path"] = path
        captured["payload"] = payload
        return {"embedding": {"values": _fake_vector(gemini_settings.EMBEDDING_DIMENSION)}}

    monkeypatch.setattr(embedding, "_gemini_post", fake_post)
    vec = embedding.embed_text("senior python engineer", task=embedding.TASK_QUERY)

    assert len(vec) == gemini_settings.EMBEDDING_DIMENSION
    assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-5  # re-normalised
    assert captured["path"].endswith(":embedContent")
    assert captured["payload"]["taskType"] == "RETRIEVAL_QUERY"
    assert captured["payload"]["outputDimensionality"] == gemini_settings.EMBEDDING_DIMENSION


def test_embed_resume_uses_query_task(gemini_settings, monkeypatch):
    captured: dict = {}

    def fake_post(path, payload):
        captured["task"] = payload["taskType"]
        return {"embedding": {"values": _fake_vector(gemini_settings.EMBEDDING_DIMENSION)}}

    monkeypatch.setattr(embedding, "_gemini_post", fake_post)
    embedding.embed_resume({"current_title": "Backend Engineer", "technical_skills": ["Python"]})
    assert captured["task"] == "RETRIEVAL_QUERY"


# ── Batch embed ──────────────────────────────────────────────────────────────

def test_embed_texts_batches_and_preserves_order(gemini_settings, monkeypatch):
    calls: list[int] = []

    def fake_post(path, payload):
        assert path.endswith(":batchEmbedContents")
        n = len(payload["requests"])
        calls.append(n)
        # Tag each vector by its in-batch position so order is verifiable.
        return {"embeddings": [
            {"values": [float(i + 1)] * gemini_settings.EMBEDDING_DIMENSION}
            for i in range(n)
        ]}

    monkeypatch.setattr(embedding, "_gemini_post", fake_post)
    texts = [f"job {i}" for i in range(embedding.GEMINI_BATCH_SIZE + 3)]
    out = embedding.embed_texts(texts)

    assert len(out) == len(texts)
    assert calls == [embedding.GEMINI_BATCH_SIZE, 3]
    # All normalised
    for v in out:
        assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-5


def test_embed_texts_non_gemini_maps_embed_text(monkeypatch):
    # Default deterministic provider: no HTTP at all.
    out = embedding.embed_texts(["a", "b"])
    assert len(out) == 2
    assert out[0] == embedding.embed_text("a")


# ── Retry behaviour ──────────────────────────────────────────────────────────

def test_gemini_retries_on_429_then_succeeds(gemini_settings, monkeypatch):
    monkeypatch.setattr(embedding.time, "sleep", lambda s: None)
    attempts = {"n": 0}

    def flaky_post(path, payload):
        attempts["n"] += 1
        if attempts["n"] < 3:
            req = httpx.Request("POST", "https://x")
            raise httpx.HTTPStatusError(
                "rate limited", request=req, response=httpx.Response(429, request=req)
            )
        return {"embedding": {"values": _fake_vector(gemini_settings.EMBEDDING_DIMENSION)}}

    monkeypatch.setattr(embedding, "_gemini_post", flaky_post)
    vec = embedding.embed_text("hello")
    assert attempts["n"] == 3
    assert len(vec) == gemini_settings.EMBEDDING_DIMENSION


def test_gemini_raises_on_non_retryable_error(gemini_settings, monkeypatch):
    def bad_post(path, payload):
        req = httpx.Request("POST", "https://x")
        raise httpx.HTTPStatusError(
            "bad request", request=req, response=httpx.Response(400, request=req)
        )

    monkeypatch.setattr(embedding, "_gemini_post", bad_post)
    with pytest.raises(httpx.HTTPStatusError):
        embedding.embed_text("hello")
