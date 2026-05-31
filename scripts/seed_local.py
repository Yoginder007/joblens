"""
Offline/local seed — populate the local SQLite DB via the real scraper +
IngestionService path, grouped by company (source = company).

Live portals (Postman, CRED, Amazon) are fetched if you have internet; the rest
use curated real postings. Either way every configured company shows up with a
working Apply link.

Usage (from backend/ so the sqlite path matches run_local.ps1):
    cd backend
    python ../scripts/seed_local.py
"""
import os
import sys

os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("DATABASE_URL", "sqlite:///./jobmatch_local.db")
os.environ.setdefault("EMBEDDING_PROVIDER", "deterministic")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("UPLOAD_DIR", "./uploads")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.domains.ingestion.scrapers import CAREER_PAGES, run_scraper_for_company  # noqa: E402
from app.domains.ingestion.service import IngestionService  # noqa: E402
from app.domains.jobs.schemas import JobCreate  # noqa: E402


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        svc = IngestionService(db)
        total_i = total_u = 0
        for company in CAREER_PAGES:
            raw = run_scraper_for_company(company)
            if not raw:
                print(f"  {company:18s} no postings (live API empty/unavailable)")
                continue
            jobs = [JobCreate(**data) for data in raw]
            inserted, updated = svc.ingest(company, jobs)
            total_i += inserted
            total_u += updated
            print(f"  {company:18s} {inserted} inserted, {updated} updated")

        print(f"\nTotal: {total_i} inserted, {total_u} updated.")
        from app.domains.jobs.models import Job
        rows = db.query(Job).all()
        print(f"Jobs in DB: {len(rows)} (all with URLs: {all(r.job_url for r in rows)})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
