"""
Production seeder — runs at deploy time (see start_prod.sh).

Idempotent: only ingests if the jobs table is empty, so redeploys don't
re-fetch. Pulls from every configured portal (live APIs + Adzuna if keys are
set + curated big-tech). Safe to run against Postgres.
"""
import logging

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.domains.ingestion.scrapers import CAREER_PAGES, run_scraper_for_company
from app.domains.ingestion.service import IngestionService
from app.domains.jobs.models import Job
from app.domains.jobs.schemas import JobCreate

logger = logging.getLogger(__name__)


def main() -> None:
    db = SessionLocal()
    try:
        existing = db.scalar(select(func.count()).select_from(Job)) or 0
        if existing > 0:
            print(f"  Jobs table already has {existing} rows — skipping seed.")
            return

        svc = IngestionService(db)
        total = 0
        for company in CAREER_PAGES:
            try:
                raw = run_scraper_for_company(company)
                if not raw:
                    continue
                jobs = [JobCreate(**data) for data in raw]
                inserted, _ = svc.ingest(company, jobs)
                total += inserted
                print(f"  {company:18s} +{inserted}")
            except Exception as exc:  # noqa: BLE001
                logger.warning("seed: %s failed: %s", company, exc)
        print(f"  Seed complete: {total} jobs ingested.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
