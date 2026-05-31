"""
Job ingestion.

On PostgreSQL, upserts are race-safe via ``INSERT ... ON CONFLICT`` on the
(source, source_id) unique constraint. On SQLite (local dev, single process) a
simple check-then-write is used — there is no concurrent writer to race with.
"""
import logging

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
