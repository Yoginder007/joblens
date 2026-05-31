"""
Celery tasks. Each opens its own session via ``SessionLocal`` (Celery runs
outside the request lifecycle, so there is no FastAPI-managed session).
"""
import logging
from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="process_resume", max_retries=3, default_retry_delay=10)
def process_resume(self, resume_id: str) -> dict:
    import uuid

    from app.domains.resumes.models import Resume
    from app.services.embedding import embed_resume
    from app.services.parsing import extract_text_from_pdf, parse_resume_text

    db = SessionLocal()
    try:
        resume = db.get(Resume, uuid.UUID(resume_id))
        if resume is None:
            return {"status": "error", "detail": "Resume not found"}

        resume.status = "processing"
        db.commit()

        resume.raw_text = extract_text_from_pdf(resume.file_path)
        resume.parsed_data = parse_resume_text(resume.raw_text)
        resume.status = "embedding"
        db.commit()

        resume.embedding = embed_resume(resume.parsed_data)
        resume.status = "ready"
        resume.error = None
        db.commit()
        return {"status": "success", "resume_id": resume_id}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        try:
            resume = db.get(Resume, uuid.UUID(resume_id))
            if resume:
                resume.status = "failed"
                resume.error = str(exc)[:500]
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        logger.exception("process_resume failed for %s", resume_id)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, name="generate_job_embedding", max_retries=3, default_retry_delay=10)
def generate_job_embedding(self, job_id: str) -> dict:
    import uuid

    from app.domains.jobs.models import Job
    from app.services.embedding import embed_job

    db = SessionLocal()
    try:
        job = db.get(Job, uuid.UUID(job_id))
        if job is None:
            return {"status": "error", "detail": "Job not found"}
        job.embedding = embed_job(job.title, job.description or "", job.technical_skills or [])
        db.commit()
        return {"status": "success", "job_id": job_id}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("generate_job_embedding failed for %s", job_id)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="run_subscriptions")
def run_subscriptions(frequency: str) -> dict:
    from app.domains.subscriptions.repository import SubscriptionRepository
    from app.domains.subscriptions.service import SubscriptionService

    db = SessionLocal()
    try:
        subs = SubscriptionRepository(db).list_active(frequency)
        service = SubscriptionService(db)
        delivered = 0
        for sub in subs:
            try:
                delivered += service.run(sub)
            except Exception:  # noqa: BLE001
                db.rollback()
                logger.exception("run_subscriptions failed for %s", sub.id)
        return {"status": "success", "frequency": frequency, "subscriptions": len(subs), "matches_sent": delivered}
    finally:
        db.close()


@celery_app.task(name="deactivate_stale_jobs")
def deactivate_stale_jobs(days_threshold: int = 30) -> dict:
    from sqlalchemy import update

    from app.domains.jobs.models import Job

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        result = db.execute(
            update(Job)
            .where(Job.is_active.is_(True), Job.scraped_at < cutoff)
            .values(is_active=False)
        )
        db.commit()
        return {"status": "success", "deactivated": result.rowcount}
    finally:
        db.close()


@celery_app.task(bind=True, name="scrape_company_jobs", max_retries=3, default_retry_delay=10)
def scrape_company_jobs(self, company_name: str) -> dict:
    from app.domains.ingestion.scrapers import run_scraper_for_company
    from app.domains.ingestion.service import IngestionService
    from app.domains.jobs.schemas import JobCreate

    db = SessionLocal()
    try:
        raw = run_scraper_for_company(company_name)
        jobs = [JobCreate(**data) for data in raw]
        # Source = company so the UI can group/filter by portal.
        inserted, updated = IngestionService(db).ingest(company_name, jobs)
        return {"status": "success", "company": company_name, "inserted": inserted, "updated": updated}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("scrape_company_jobs failed for %s", company_name)
        raise self.retry(exc=exc)
    finally:
        db.close()
