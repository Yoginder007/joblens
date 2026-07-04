import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ConflictError
from app.core.params import csv as _csv
from app.domains.candidates.dependencies import CurrentCandidate
from app.domains.jobs.repository import JobFilters
from app.domains.matching.schemas import EligibleJobsResponse, MatchesResponse
from app.domains.matching.service import MatchingService
from app.domains.resumes.models import Resume
from app.domains.resumes.service import ResumeService

router = APIRouter(prefix="/api/jobs", tags=["Matching"])


def _ready_resume(db: Session, resume_id: uuid.UUID, candidate, require_embedding: bool) -> Resume:
    resume = ResumeService(db).get_owned(resume_id, candidate.id)
    if resume.status != "ready":
        raise ConflictError(f"Resume is not ready (status: {resume.status})")
    if require_embedding and (resume.embedding is None or len(resume.embedding) == 0):
        raise ConflictError("Resume embedding is missing")
    return resume


@router.get("/matches", response_model=MatchesResponse)
def get_matches(
    candidate: CurrentCandidate,
    resume_id: uuid.UUID,
    companies: str | None = None,
    location: str | None = None,
    location_type: str | None = None,
    work_model: str | None = None,
    min_score: float = Query(0.0, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Vector ANN + scalar filters, scored and grouped by company. Persists matches."""
    resume = _ready_resume(db, resume_id, candidate, require_embedding=True)
    filters = JobFilters(
        location=location, work_model=work_model, location_type=location_type,
        companies=_csv(companies),
    )
    return MatchingService(db).run_matches(resume, filters, limit, min_score)


@router.get("/eligible", response_model=EligibleJobsResponse)
def get_eligible(
    candidate: CurrentCandidate,
    resume_id: uuid.UUID,
    location: str | None = None,
    title_keyword: str | None = None,
    experience_min: int = Query(0, ge=0),
    max_experience: int | None = Query(None, ge=0),
    work_model: str | None = None,
    job_type: str | None = None,
    roles: str | None = None,
    posted_within_days: int | None = Query(None, ge=1, le=365),
    sources: str | None = None,
    match_mode: str = Query("semantic", pattern="^(semantic|direct)$"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Jobs the candidate qualifies for (experience hard filter), scored + ranked.

    All scalar controls map to real ``JobFilters`` columns so the UI filters are
    functional, not decorative. ``match_mode=direct`` scores on skill overlap
    alone (filter-driven); ``semantic`` blends vector similarity + skills.
    """
    resume = _ready_resume(db, resume_id, candidate, require_embedding=False)
    filters = JobFilters(
        q=title_keyword,
        location=location,
        experience_min=experience_min,
        experience_max=max_experience,
        work_model=work_model,
        job_type=job_type,
        role_categories=_csv(roles),
        posted_within_days=posted_within_days,
        sources=_csv(sources),
    )
    return MatchingService(db).eligible(resume, filters, limit, match_mode=match_mode)
