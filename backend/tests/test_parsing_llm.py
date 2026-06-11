"""Unit tests for the LLM resume parser (HTTP mocked - no network)."""
import json
import os

import pytest

os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("EMBEDDING_PROVIDER", "deterministic")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

from app.core.config import Settings, get_settings  # noqa: E402
from app.services import gemini as gemini_svc  # noqa: E402
from app.services import parsing  # noqa: E402

RESUME_TEXT = (
    "Jane Doe\nSenior Backend Engineer\n"
    "5 years of experience with Python, FastAPI and PostgreSQL on AWS.\n"
    "Education: B.Tech CSE, NIT Trichy, 2019"
)


def _llm_response(payload: dict) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}


@pytest.fixture
def llm_settings(monkeypatch):
    settings = get_settings().model_copy(
        update={"RESUME_PARSER": "gemini", "GOOGLE_API_KEY": "test-key"}
    )
    monkeypatch.setattr(parsing, "get_settings", lambda: settings, raising=False)
    # parse_resume_text imports get_settings lazily from app.core.config
    import app.core.config as config_mod
    monkeypatch.setattr(config_mod, "get_settings", lambda: settings)
    return settings


def test_config_guard_requires_key_for_llm_parser():
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        Settings(RESUME_PARSER="gemini", GOOGLE_API_KEY="", _env_file=None)


def test_llm_parse_happy_path(llm_settings, monkeypatch):
    captured: dict = {}

    def fake_post(path, payload):
        captured["path"] = path
        captured["payload"] = payload
        return _llm_response({
            "full_name": "Jane Doe",
            "current_title": "Senior Backend Engineer",
            "total_years_experience": 5,
            "technical_skills": [
                {"category": "Languages", "skills": ["Python", " SQL ", ""]},
                {"category": "Frameworks", "skills": ["FastAPI", "python"]},  # dupe (case)
            ],
            "domain_expertise": ["Backend", "Cloud"],
            "education": ["B.Tech CSE, NIT Trichy, 2019"],
            "certifications": [],
        })

    monkeypatch.setattr(gemini_svc, "gemini_post", fake_post)
    out = parsing.parse_resume_text(RESUME_TEXT)

    assert out["parser"] == "gemini"
    assert out["full_name"] == "Jane Doe"
    assert out["total_years_experience"] == 5
    # structured output requested
    gen = captured["payload"]["generationConfig"]
    assert gen["responseMimeType"] == "application/json"
    assert "responseSchema" in gen
    # blank skill dropped, cross-category dupe (case-insensitive) dropped
    langs = next(c for c in out["technical_skills"] if c["category"] == "Languages")
    frams = next(c for c in out["technical_skills"] if c["category"] == "Frameworks")
    assert langs["skills"] == ["Python", "SQL"]
    assert frams["skills"] == ["FastAPI"]


def test_llm_parse_clamps_garbage_years(llm_settings, monkeypatch):
    def fake_post(path, payload):
        return _llm_response({
            "current_title": "Engineer",
            "total_years_experience": 9999,
            "technical_skills": [],
        })

    monkeypatch.setattr(gemini_svc, "gemini_post", fake_post)
    out = parsing.parse_resume_text(RESUME_TEXT)
    assert out["total_years_experience"] == 50          # clamped
    assert out["technical_skills"][0]["category"] == "General"  # empty -> default


def test_llm_failure_falls_back_to_regex(llm_settings, monkeypatch):
    def boom(path, payload):
        raise RuntimeError("quota exhausted")

    monkeypatch.setattr(gemini_svc, "gemini_post", boom)
    monkeypatch.setattr(gemini_svc.time, "sleep", lambda s: None)
    out = parsing.parse_resume_text(RESUME_TEXT)
    assert out["parser"] == "regex"
    assert out["total_years_experience"] == 5  # regex still extracts years


def test_regex_parser_is_default():
    out = parsing.parse_resume_text(RESUME_TEXT)
    assert out["parser"] == "regex"
