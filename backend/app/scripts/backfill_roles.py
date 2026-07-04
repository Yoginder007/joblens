"""
One-off maintenance: (re)classify every job's role_category with the current
taxonomy and, when INGEST_TECH_ONLY is set, deactivate non-engineering rows
that slipped in before the ingestion guard existed.

Run after deploying the role-taxonomy release (works on SQLite and Postgres):

    cd backend
    python -m app.scripts.backfill_roles
"""
import logging

from sqlalchemy import select

import app.db.base  # noqa: F401  (registers all mappers)
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.domains.jobs.models import Job
from app.services.roles import classify_role

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
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
        logger.info(
            "Backfill done: %d jobs scanned, %d reclassified, %d non-tech deactivated.",
            len(jobs), reclassified, deactivated,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
