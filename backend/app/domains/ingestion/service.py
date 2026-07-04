"""
Job ingestion.

On PostgreSQL, upserts are race-safe via ``INSERT ... ON CONFLICT`` on the
(source, source_id) unique constraint. On SQLite (local dev, single process) a
simple check-then-write is used — there is no concurrent writer to race with.
"""
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.upsert import upsert
from app.domains.jobs.models import Job
from app.domains.jobs.schemas import JobCreate
from app.services.roles import classify_role

logger = logging.getLogger(__name__)

# Columns refreshed when a job is re-ingested. Includes job_url so a posting
# whose link changes (or was seeded without one) gets corrected on re-sync,
# and last_seen_at so freshness/staleness track "still live in the feed",
# not "first scraped". source/source_id are the identity and are never updated.
_UPDATE_KEYS = (
    "title", "description", "technical_skills", "location",
    "work_model", "is_remote", "job_type", "is_active",
    "required_experience_years", "job_url", "salary_min", "salary_max",
    "industry", "company_rating", "company_size",
    "role_category", "last_seen_at",
)


class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    def ingest(self, source: str, jobs: list[JobCreate]) -> tuple[int, int]:
        """Upsert jobs. Returns (inserted, updated). New jobs get embeddings queued."""
        inserted = updated = 0
        new_ids: list[str] = []

        now = datetime.now(timezone.utc)
        for j in jobs:
            values = dict(
                title=j.title, company=j.company, description=j.description,
                required_experience_years=j.required_experience_years,
                technical_skills=j.technical_skills, salary_min=j.salary_min,
                salary_max=j.salary_max, location=j.location, job_url=j.job_url,
                source=source, source_id=j.source_id,
                work_model=j.work_model or "on-site", industry=j.industry,
                company_rating=j.company_rating, company_size=j.company_size,
                # job_type stays as reported (None = unknown, not fabricated).
                job_type=j.job_type, is_remote=j.is_remote,
                role_category=j.role_category or classify_role(j.title),
                last_seen_at=now,
                is_active=True,
            )
            job_id, was_inserted = upsert(
                self.db, Job, values,
                conflict_constraint="uq_job_source_id",
                update_cols=_UPDATE_KEYS,
                match_by=("source", "source_id"),
            )
            if was_inserted:
                inserted += 1
                new_ids.append(str(job_id))
            else:
                updated += 1

        self.db.commit()

        # The option catalogue (dropdown values) may have changed.
        from app.domains.jobs.service import invalidate_options_cache

        invalidate_options_cache()

        if new_ids:
            from app.workers.tasks import generate_job_embedding

            for job_id in new_ids:
                generate_job_embedding.delay(job_id)

        logger.info(
            "Ingest from %s: %d inserted, %d updated (%d received)",
            source, inserted, updated, len(jobs),
        )
        return inserted, updated


# ── Full ingestion run (scheduled refresh / admin) ───────────────────────────
# One function both the sync API path and the background path share. The
# scheduled GitHub Actions workflow triggers it in background mode because
# fetching 20 portals can exceed the free-tier proxy timeout.

INGEST_STATUS: dict = {"state": "idle"}


def ingest_all(companies: list[str] | None = None, tier: str = "all", force: bool = False) -> dict:
    """Fetch + upsert jobs. With ``companies=None`` runs the portals of the given
    cost ``tier`` ('free' | 'paid' | 'all'). Paid (Apify) sources are throttled
    to a weekly cadence — if the most recent paid run is < 7 days old they're
    skipped unless ``force`` is set. Opens its own session; mirrors progress into
    INGEST_STATUS."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func

    from app.core.database import SessionLocal
    from app.domains.ingestion.models import ScrapeRun
    from app.domains.ingestion.scrapers import (
        CAREER_PAGES,
        _PAID_ATS,
        companies_by_tier,
        run_scraper_for_company,
    )

    todo = list(companies) if companies is not None else companies_by_tier(tier)
    status = INGEST_STATUS
    status.update(state="running", done=0, total=len(todo), error=None, skipped_paid=[])

    db = SessionLocal()
    try:
        # Cost guard: don't re-run paid (Apify) sources more than once a week.
        paid = [c for c in todo if CAREER_PAGES.get(c, {}).get("ats") in _PAID_ATS]
        if paid and not force:
            last = db.scalar(select(func.max(ScrapeRun.run_at)).where(ScrapeRun.tier == "paid"))
            if last is not None:
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - last < timedelta(days=7):
                    logger.info(
                        "Skipping paid sources %s (last paid run %s, < 7d). Pass force=true to override.",
                        paid, last.isoformat(),
                    )
                    status["skipped_paid"] = paid
                    todo = [c for c in todo if c not in paid]
                    paid = []
        status["total"] = len(todo)

        svc = IngestionService(db)
        results: list[dict] = []
        for company in todo:
            try:
                raw = run_scraper_for_company(company)
                jobs = [JobCreate(**data) for data in raw]
                inserted, updated = svc.ingest(company, jobs)
                results.append({"company": company, "inserted": inserted,
                                "updated": updated, "error": None})
            except Exception as exc:  # noqa: BLE001
                logger.exception("Ingest failed for %s", company)
                db.rollback()
                results.append({"company": company, "inserted": 0, "updated": 0,
                                "error": str(exc)[:200]})
            status["done"] = len(results)
            status["results"] = results

        # Record a ledger row only for a productive paid run, so the weekly guard
        # throttles real runs but a failed/empty paid attempt can be retried.
        if paid:
            ran = [r for r in results if r["company"] in paid]
            returned = sum(r["inserted"] + r["updated"] for r in ran)
            if returned > 0:
                db.add(ScrapeRun(
                    tier="paid",
                    companies=[r["company"] for r in ran],
                    inserted=sum(r["inserted"] for r in ran),
                    updated=sum(r["updated"] for r in ran),
                    returned=returned,
                ))
                db.commit()

        status["state"] = "done"
        return {
            "results": results,
            "total_inserted": sum(r["inserted"] for r in results),
            "total_updated": sum(r["updated"] for r in results),
            "skipped_paid": status.get("skipped_paid", []),
        }
    except Exception as exc:  # noqa: BLE001
        status.update(state="failed", error=str(exc)[:300])
        raise
    finally:
        db.close()


# ── Role backfill (taxonomy migrations) ─────────────────────────────────────
# (Re)classifies every job with the CURRENT taxonomy rules and, when
# INGEST_TECH_ONLY is set, deactivates non-engineering rows that predate the
# ingestion guard. Exposed as an API endpoint because the free hosting tier
# has no shell; app/scripts/backfill_roles.py wraps it for local/CLI use.


def backfill_roles() -> dict:
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.services.roles import classify_role

    tech_only = get_settings().INGEST_TECH_ONLY
    db = SessionLocal()
    try:
        jobs = db.scalars(select(Job)).all()
        reclassified = deactivated = 0
        for job in jobs:
            role = classify_role(job.title)
            if job.role_category != role:
                job.role_category = role
                reclassified += 1
            if tech_only and role == "Other" and job.is_active:
                job.is_active = False
                deactivated += 1
        db.commit()

        from app.domains.jobs.service import invalidate_options_cache

        invalidate_options_cache()
        result = {
            "status": "success",
            "scanned": len(jobs),
            "reclassified": reclassified,
            "deactivated_non_tech": deactivated,
        }
        logger.info("Role backfill: %s", result)
        return result
    finally:
        db.close()


# ── Re-embedding (provider migrations) ───────────────────────────────────────
# Regenerates every vector with the CURRENT embedding provider. Needed once
# after switching providers (e.g. deterministic → gemini): vectors from
# different providers live in incompatible spaces, so they must all be redone
# together. Runs as a FastAPI background task on free tiers with no shell —
# progress is exposed via REEMBED_STATUS.

REEMBED_STATUS: dict = {"state": "idle"}


def reembed_all(limit: int | None = None, pause_s: float = 15.0) -> dict:
    """Re-embed active jobs (RETRIEVAL_DOCUMENT) and ready résumés
    (RETRIEVAL_QUERY) in batches, pausing between batches to respect the
    free-tier tokens-per-minute budget. Opens its own session (runs outside
    the request lifecycle). Returns counts; mirrors progress in REEMBED_STATUS."""
    import app.db.base  # noqa: F401  (registers all mappers for CLI usage)
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.domains.resumes.models import Resume
    from app.services.embedding import (
        GEMINI_BATCH_SIZE,
        TASK_QUERY,
        embed_resume,
        embed_texts,
        job_embedding_text,
    )

    settings = get_settings()
    status = REEMBED_STATUS
    status.update(state="running", provider=settings.EMBEDDING_PROVIDER,
                  jobs_done=0, jobs_total=0, resumes_done=0, error=None)

    db = SessionLocal()
    try:
        jobs = db.scalars(
            select(Job).where(Job.is_active.is_(True)).order_by(Job.scraped_at.desc())
        ).all()
        if limit is not None:
            jobs = jobs[:limit]
        status["jobs_total"] = len(jobs)

        pause = pause_s if settings.EMBEDDING_PROVIDER == "gemini" else 0.0
        for i in range(0, len(jobs), GEMINI_BATCH_SIZE):
            chunk = jobs[i:i + GEMINI_BATCH_SIZE]
            texts = [
                job_embedding_text(j.title, j.description or "", j.technical_skills or [])
                for j in chunk
            ]
            vectors = embed_texts(texts)
            for job, vec in zip(chunk, vectors):
                job.embedding = vec
            db.commit()
            status["jobs_done"] = min(i + GEMINI_BATCH_SIZE, len(jobs))
            logger.info("Re-embed: %d/%d jobs", status["jobs_done"], len(jobs))
            if pause and i + GEMINI_BATCH_SIZE < len(jobs):
                time.sleep(pause)

        resumes = db.scalars(
            select(Resume).where(Resume.status == "ready")
        ).all()
        if limit is not None:
            resumes = resumes[:limit]
        for resume in resumes:
            if resume.parsed_data:
                resume.embedding = embed_resume(resume.parsed_data)
                status["resumes_done"] = status.get("resumes_done", 0) + 1
        db.commit()
        logger.info("Re-embed: %d resumes (task=%s)", status["resumes_done"], TASK_QUERY)

        status["state"] = "done"
        return {
            "jobs": status["jobs_done"],
            "resumes": status["resumes_done"],
            "provider": settings.EMBEDDING_PROVIDER,
        }
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        status.update(state="failed", error=str(exc)[:300])
        logger.exception("Re-embed failed")
        raise
    finally:
        db.close()
