import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.domains.candidates.models import Candidate
from app.domains.jobs.models import Job
from app.domains.resumes.models import Resume

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    settings = get_settings()
    db_ok = False
    stats: dict[str, int] = {}
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
        stats = {
            "active_jobs": db.scalar(
                select(func.count()).select_from(Job).where(Job.is_active.is_(True))
            ),
            "candidates": db.scalar(select(func.count()).select_from(Candidate)),
            "ready_resumes": db.scalar(
                select(func.count()).select_from(Resume).where(Resume.status == "ready")
            ),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB health check failed: %s", exc)

    return {
        "status": "healthy" if db_ok else "degraded",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "connected" if db_ok else "unreachable",
        **stats,
    }
