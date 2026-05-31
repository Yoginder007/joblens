"""Unit tests for career-page URL parsing → job ID extraction (no network)."""
import pytest

from app.domains.ingestion.scrapers import (
    available_portals,
    extract_board_token,
    extract_job_id_from_url,
    extract_skills,
    is_valid_job_url,
    run_scraper_for_company,
    strip_html,
)


@pytest.mark.parametrize("url, expected", [
    ("https://boards.greenhouse.io/razorpay", "razorpay"),
    ("https://boards.greenhouse.io/razorpay/jobs/5512345", "razorpay"),
    ("https://jobs.lever.co/cred/", "cred"),
    ("https://jobs.lever.co/atlassian/2b8c-uuid", "atlassian"),
    ("https://www.uber.com/global/en/careers/list/", None),
    ("", None),
])
def test_extract_board_token(url, expected):
    assert extract_board_token(url) == expected


@pytest.mark.parametrize("url, expected", [
    ("https://www.amazon.jobs/en/jobs/10428414/sde-1", "10428414"),
    ("https://www.amazon.jobs/en/jobs/10423408/software-development-engineer", "10423408"),
    ("https://boards.greenhouse.io/razorpay/jobs/5512345", "5512345"),
    ("https://www.uber.com/global/en/careers/list/136541/", "136541"),
    ("https://jobs.lever.co/cred/2b8c9d1e-4f5a-6b7c-8d9e-0f1a2b3c4d5e",
     "2b8c9d1e-4f5a-6b7c-8d9e-0f1a2b3c4d5e"),
    ("https://razorpay.com/jobs/", None),       # career-root, no specific id
    ("https://www.uber.com/careers/", None),
    ("", None),
])
def test_extract_job_id_from_url(url, expected):
    assert extract_job_id_from_url(url) == expected


def test_is_valid_job_url_rejects_career_roots(monkeypatch):
    # Career-root pages have no posting id → invalid regardless of environment.
    assert is_valid_job_url("https://razorpay.com/jobs/") is False
    assert is_valid_job_url("") is False


def test_is_valid_job_url_accepts_specific_posting():
    # Local/deterministic env bypasses the live HEAD check.
    assert is_valid_job_url("https://www.amazon.jobs/en/jobs/10428414/sde-1") is True


def test_strip_html():
    assert strip_html("<p>Hello<br>World</p>") == "Hello\nWorld"
    assert strip_html("Plain &amp; clean") == "Plain & clean"


@pytest.mark.parametrize("text, expected_subset", [
    ("We use Python, Go and Kubernetes daily.", {"Python", "Go", "Kubernetes"}),
    ("Strong Java and Spring Boot background; AWS a plus.", {"Java", "Spring", "AWS"}),
    ("Golang microservices on GCP.", {"Go", "Microservices", "GCP"}),
    ("No tech here.", set()),
])
def test_extract_skills(text, expected_subset):
    found = set(extract_skills(text))
    assert expected_subset.issubset(found)


def test_extract_skills_avoids_substring_false_positives():
    # "R" must not match inside ordinary words; "Go" must not match "Google".
    found = set(extract_skills("Google good morning narrative"))
    assert "Go" not in found
    assert "R" not in found


def test_available_portals_shape():
    portals = available_portals()
    names = {p["company"] for p in portals}
    # All user-provided companies are represented.
    assert {"Postman", "CRED", "Amazon", "Uber", "Razorpay", "Goldman Sachs", "Visa"} <= names
    # Curated companies are marked non-live and still carry a careers URL.
    razorpay = next(p for p in portals if p["company"] == "Razorpay")
    assert razorpay["live"] is False
    assert razorpay["careers_url"].startswith("http")


def test_curated_company_returns_real_posting():
    # No network needed: curated provider returns verified postings.
    jobs = run_scraper_for_company("Goldman Sachs")
    assert len(jobs) >= 1
    j = jobs[0]
    assert j["company"] == "Goldman Sachs"
    assert j["job_url"].startswith("http")
    assert j["technical_skills"]
