"""Repository-level filter/facet tests on in-memory SQLite.

These cover the filter semantics the UI depends on — the exact layer where the
"Fresher preset does nothing" and "re-scraped jobs age out" bugs lived.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.base  # noqa: F401  (registers all models on Base.metadata)
from app.core.database import Base
from app.domains.jobs.models import Job
from app.domains.jobs.repository import JobFilters, JobRepository


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _job(**overrides) -> Job:
    now = datetime.now(timezone.utc)
    defaults = dict(
        title="Software Engineer",
        company="Acme",
        description="Build things.",
        required_experience_years=3,
        technical_skills=["Python"],
        location="Bengaluru, India",
        job_url="https://example.com/jobs/1",
        source="Acme",
        source_id=f"T-{overrides.get('title', 'x')}-{overrides.get('required_experience_years', 0)}",
        work_model="on-site",
        is_remote=False,
        role_category="Software Engineering",
        scraped_at=now,
        last_seen_at=now,
        is_active=True,
    )
    defaults.update(overrides)
    return Job(**defaults)


def test_experience_max_zero_is_a_real_filter(db):
    """The Fresher preset (min=0, max=0) must return only 0-experience jobs."""
    db.add(_job(source_id="a", required_experience_years=0))
    db.add(_job(source_id="b", required_experience_years=5))
    db.commit()

    repo = JobRepository(db)
    fresher = repo.search(JobFilters(experience_min=0, experience_max=0), "date", 10, 0)
    assert [j.required_experience_years for j in fresher] == [0]
    # And None still means "no upper bound".
    all_jobs = repo.search(JobFilters(experience_min=0, experience_max=None), "date", 10, 0)
    assert len(all_jobs) == 2


def test_posted_within_uses_last_seen_not_first_scrape(db):
    """A posting continuously re-scraped stays 'fresh' even if first seen long ago."""
    now = datetime.now(timezone.utc)
    db.add(_job(source_id="old-but-live", scraped_at=now - timedelta(days=90), last_seen_at=now))
    db.add(_job(source_id="gone", scraped_at=now - timedelta(days=90),
                last_seen_at=now - timedelta(days=60)))
    db.commit()

    repo = JobRepository(db)
    fresh = repo.search(JobFilters(posted_within_days=7), "date", 10, 0)
    assert [j.source_id for j in fresh] == ["old-but-live"]


def test_role_category_filter_and_facets(db):
    db.add(_job(source_id="be", title="Backend Engineer", role_category="Backend"))
    db.add(_job(source_id="fe", title="Frontend Engineer", role_category="Frontend"))
    db.add(_job(source_id="ml", title="ML Engineer", role_category="ML / AI"))
    db.commit()

    repo = JobRepository(db)
    only_be = repo.search(JobFilters(role_categories=["Backend"]), "date", 10, 0)
    assert [j.source_id for j in only_be] == ["be"]

    multi = repo.search(JobFilters(role_categories=["Backend", "Frontend"]), "date", 10, 0)
    assert {j.source_id for j in multi} == {"be", "fe"}

    facets = repo.facets(JobFilters())
    assert facets.roles == {"Backend": 1, "Frontend": 1, "ML / AI": 1}


def test_filter_options_include_taxonomy_ordered_roles(db):
    db.add(_job(source_id="ml", role_category="ML / AI"))
    db.add(_job(source_id="be", role_category="Backend"))
    db.commit()

    opts = JobRepository(db).filter_options()
    assert opts["roles"] == ["Backend", "ML / AI"]  # canonical taxonomy order


def test_relevance_sort_ranks_title_hits_first(db):
    db.add(_job(source_id="title-hit", title="Backend Engineer",
                description="nothing relevant"))
    db.add(_job(source_id="desc-hit", title="Platform Role",
                description="we need a backend person"))
    db.commit()

    repo = JobRepository(db)
    ranked = repo.search(JobFilters(q="backend"), "relevance", 10, 0)
    assert [j.source_id for j in ranked] == ["title-hit", "desc-hit"]


def test_ingest_upsert_refreshes_last_seen(db, monkeypatch):
    """Re-ingesting the same posting must bump last_seen_at (staleness anchor)."""
    from app.domains.ingestion.service import IngestionService
    from app.domains.jobs.schemas import JobCreate

    # No embedding tasks in this unit test.
    import app.workers.tasks as tasks

    monkeypatch.setattr(tasks.generate_job_embedding, "delay", lambda *a, **k: None)

    payload = JobCreate(
        title="Backend Engineer", company="Acme", description="Build APIs.",
        source_id="X-1", job_url="https://example.com/jobs/9",
    )
    svc = IngestionService(db)
    inserted, updated = svc.ingest("Acme", [payload])
    assert (inserted, updated) == (1, 0)

    job = db.query(Job).one()
    first_seen = job.last_seen_at
    assert job.role_category == "Backend"  # classified at ingest even w/o scraper tag

    # Simulate the passage of time, then re-ingest the same posting.
    job.last_seen_at = first_seen - timedelta(days=10)
    db.commit()

    inserted, updated = svc.ingest("Acme", [payload])
    assert (inserted, updated) == (0, 1)
    db.refresh(job)
    assert job.last_seen_at > first_seen - timedelta(days=1)
    # scraped_at (first-seen) is NOT rewritten by re-ingest.
    assert job.scraped_at is not None
