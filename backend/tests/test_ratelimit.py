"""RateLimiter unit tests (enabled explicitly — conftest disables it globally)."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.core.ratelimit as rl


def _request(ip: str = "203.0.113.7"):
    return SimpleNamespace(client=SimpleNamespace(host=ip))


@pytest.fixture()
def enabled(monkeypatch):
    monkeypatch.setattr(rl, "get_settings", lambda: SimpleNamespace(RATE_LIMIT_ENABLED=True))


def test_limit_enforced_per_ip(enabled):
    limiter = rl.RateLimiter(3, 60.0)
    for _ in range(3):
        limiter(_request())
    with pytest.raises(HTTPException) as exc:
        limiter(_request())
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers

    # A different client IP is unaffected.
    limiter(_request("198.51.100.1"))


def test_window_expiry_frees_budget(enabled, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(rl.time, "monotonic", lambda: now[0])
    limiter = rl.RateLimiter(2, 10.0)
    limiter(_request())
    limiter(_request())
    with pytest.raises(HTTPException):
        limiter(_request())
    now[0] += 11.0  # window rolls over
    limiter(_request())  # allowed again


def test_disabled_is_a_noop(monkeypatch):
    monkeypatch.setattr(rl, "get_settings", lambda: SimpleNamespace(RATE_LIMIT_ENABLED=False))
    limiter = rl.RateLimiter(1, 60.0)
    for _ in range(5):
        limiter(_request())  # never raises
