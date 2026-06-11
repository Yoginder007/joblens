"""
Job ingestion.

On PostgreSQL, upserts are race-safe via ``INSERT ... ON CONFLICT`` on the
(source, source_id) unique constraint. On SQLite (local dev, single process) a
simple check-then-write is used — there is no concurrent writer to race with.
"""
import logging
import time

from sqlalchemy import literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domains.jobs.models import Job
from app.domains.jobs.schemas import JobCreate

logger = logging.getLogger(__name__)

# Columns refreshed when a job is re-ingested. Includes job_url so a posting
# whose link changes (or was seeded without one) gets corrected on re-sync.
# source/source_id are the identity and are never updated.
_UPDATE_KEYS = (
    "title", "description", "technical_skills", "location",
    "work_model", "is_remote", "job_type", "is_active",
    "required_experience_years", "job_url", "salary_min", "salary_max",
    "industry", "company_rating", "company_size",
)


class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    def ingest(self, source: str, jobs: list[JobCreate]) -> tuple[int, int]:
        """Upsert jobs. Returns (inserted, updated). New jobs get embeddings queued."""
        is_pg = self.db.bind.dialect.name == "postgresql"
        inserted = updated = 0
        new_ids: list[str] = []

        for j in jobs:
            values = dict(
                title=j.title, company=j.company, description=j.description,
                required_experience_years=j.required_experience_years,
                technical_skills=j.technical_skills, salary_min=j.salary_min,
                salary_max=j.salary_max, location=j.location, job_url=j.job_url,
                source=source, source_id=j.source_id,
                work_model=j.work_model or "on-site", industry=j.industry,
                company_rating=j.company_rating, company_size=j.company_size,
                job_type=j.job_type or "full-time", is_remote=j.is_remote,
                is_active=True,
            )
            if is_pg:
                stmt = (
                    pg_insert(Job).values(**values)
                    .on_conflict_do_update(
                        constraint="uq_job_source_id",
                        set_={k: values[k] for k in _UPDATE_KEYS},
                    )
                    .returning(Job.id, literal_column("(xmax = 0)").label("inserted"))
                )
                row = self.db.execute(stmt).one()
                was_inserted, job_id = bool(row.inserted), row.id
            else:
                existing = self.db.scalar(
                    select(Job).where(Job.source == source, Job.source_id == j.source_id)
                )
                if existing:
                    for k in _UPDATE_KEYS:
                        setattr(existing, k, values[k])
                    was_inserted, job_id = False, existing.id
                else:
                    job = Job(**values)
                    self.db.add(job)
                    self.db.flush()
                    was_inserted, job_id = True, job.id

            if was_inserted:
                inserted += 1
                new_ids.append(str(job_id))
            else:
                updated += 1

        self.db.commit()

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


def ingest_all(companies: list[str] | None = None) -> dict:
    """Fetch + upsert jobs for the given companies (all configured if None).
    Opens its own session; mirrors progress into INGEST_STATUS."""
    from app.core.database import SessionLocal
    from app.domains.ingestion.scrapers import CAREER_PAGES, run_scraper_for_company

    todo = companies or list(CAREER_PAGES.keys())
    status = INGEST_STATUS
    status.update(state="running", done=0, total=len(todo), error=None)

    db = SessionLocal()
    try:
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
        status["state"] = "done"
        return {
            "results": results,
            "total_inserted": sum(r["inserted"] for r in results),
            "total_updated": sum(r["updated"] for r in results),
        }
    except Exception as exc:  # noqa: BLE001
        status.update(state="failed", error=str(exc)[:300])
        raise
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
