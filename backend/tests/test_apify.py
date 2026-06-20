"""Unit tests for the Apify LinkedIn/Indeed providers (mapping + disabled path,
no network)."""
import os

os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("EMBEDDING_PROVIDER", "deterministic")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

from app.domains.ingestion import scrapers  # noqa: E402
from app.domains.ingestion.scrapers import available_portals, run_scraper_for_company  # noqa: E402


def test_apify_disabled_returns_empty_without_network():
    # No APIFY_TOKEN in the test env → fetchers short-circuit before any HTTP.
    assert run_scraper_for_company("LinkedIn") == []
    assert run_scraper_for_company("Indeed") == []


def test_portals_include_linkedin_and_indeed():
    portals = {p["company"]: p for p in available_portals()}
    assert "LinkedIn" in portals and "Indeed" in portals
    # Aggregators are marked live and carry a real careers URL.
    assert portals["LinkedIn"]["live"] is True
    assert portals["LinkedIn"]["careers_url"].startswith("http")


def test_apify_map_linkedin_item():
    item = {
        "title": "Senior Backend Engineer",
        "companyName": "Stripe",
        "location": "Bengaluru, India",
        "jobUrl": "https://www.linkedin.com/jobs/view/3812345678",
        "description": "Build APIs with Python, Go and Kubernetes.",
        "id": "3812345678",
    }
    job = scrapers._apify_map(item, "LI")
    assert job["title"] == "Senior Backend Engineer"
    assert job["company"] == "Stripe"
    assert job["job_url"].endswith("3812345678")
    assert job["source_id"] == "LI-3812345678"
    assert {"Python", "Go", "Kubernetes"}.issubset(set(job["technical_skills"]))


def test_apify_map_indeed_alt_field_names():
    # Indeed actors use different keys (positionName/company/url/descriptionText).
    item = {
        "positionName": "Software Developer",
        "company": "Razorpay",
        "location": "Remote, India",
        "url": "https://in.indeed.com/viewjob?jk=abcdef123456",
        "descriptionText": "Java and Spring Boot microservices.",
    }
    job = scrapers._apify_map(item, "IND")
    assert job["company"] == "Razorpay"
    assert job["location"] == "Remote, India"
    assert job["source_id"].startswith("IND-")  # stable hashed id from the URL


def test_apify_map_nested_company_and_location_dicts():
    item = {
        "title": "ML Engineer",
        "company": {"name": "NVIDIA"},
        "location": {"displayName": "Pune, India"},
        "url": "https://example.com/jobs/42",
        "description": "PyTorch and CUDA.",
    }
    job = scrapers._apify_map(item, "LI")
    assert job["company"] == "NVIDIA"
    assert job["location"] == "Pune, India"


def test_apify_map_requires_title():
    assert scrapers._apify_map({"companyName": "X", "url": "https://x.com/1"}, "LI") is None


def test_apify_source_id_is_stable_for_same_url():
    # Same posting (no explicit id) must produce the same source_id across runs
    # so re-ingestion upserts instead of duplicating.
    item = {"title": "Dev", "url": "https://in.indeed.com/viewjob?jk=zzz"}
    a = scrapers._apify_map(item, "IND")["source_id"]
    b = scrapers._apify_map(item, "IND")["source_id"]
    assert a == b


def test_companies_by_tier_splits_free_and_paid():
    from app.domains.ingestion.scrapers import companies_by_tier

    free = set(companies_by_tier("free"))
    paid = set(companies_by_tier("paid"))
    allc = set(companies_by_tier("all"))
    # Only the Apify portals are paid.
    assert paid == {"LinkedIn", "Indeed"}
    assert not (paid & free)
    # Free tier keeps the ATS boards + Adzuna + curated.
    assert {"Adzuna", "Postman", "Goldman Sachs"} <= free
    assert allc == free | paid
