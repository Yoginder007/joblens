"""
Offline/local seed — populate the local SQLite DB via the real scraper +
IngestionService path, grouped by company (source = company).

Live portals (Postman, CRED, Amazon) are fetched if you have internet; the rest
use curated real postings. Either way every configured company shows up with a
working Apply link.

Usage (from backend/ so the sqlite path matches run_local.ps1):
    cd backend
    python ../scripts/seed_local.py            # FREE sources only (default)
    python ../scripts/seed_local.py --all      # include paid Apify sources ($)
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
from app.domains.ingestion.scrapers import companies_by_tier, run_scraper_for_company  # noqa: E402
from app.domains.ingestion.service import IngestionService  # noqa: E402
from app.domains.jobs.schemas import JobCreate  # noqa: E402


def main() -> None:
    # Paid (Apify pay-per-result) sources only on explicit request — a routine
    # local reseed must never bill the Apify account by accident.
    tier = "all" if "--all" in sys.argv else "free"
    companies = companies_by_tier(tier)
    if tier == "free":
        print("Seeding FREE sources only (pass --all to include paid Apify sources).\n")

    init_db()
    db = SessionLocal()
    try:
        svc = IngestionService(db)
        total_i = total_u = 0
        for company in companies:
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
