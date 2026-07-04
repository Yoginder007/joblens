import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.params import csv as _csv
from app.domains.jobs.repository import JobFilters
from app.domains.jobs.schemas import JobResponse, JobSearchResponse
from app.domains.jobs.service import JobService

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


class FilterOptions(BaseModel):
    locations: list[str] = []
    countries: list[str] = []
    industries: list[str] = []
    titles: list[str] = []
    companies: list[str] = []
    sources: list[str] = []
    work_models: list[str] = []
    job_types: list[str] = []
    roles: list[str] = []


@router.get("/options", response_model=FilterOptions)
def filter_options(db: Session = Depends(get_db)):
    """Distinct filter values from the live job data, for the home dropdowns."""
    return JobService(db).filter_options()


@router.get("/recent", response_model=list[JobResponse])
def recent_jobs(
    days: int = Query(60, ge=1, le=365),
    source: str | None = None,
    location: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return JobService(db).recent(days, source, location, limit)


@router.get("/search", response_model=JobSearchResponse)
def search_jobs(
    q: str | None = None,
    location: str | None = None,
    work_model: str | None = None,
    salary_min: int | None = Query(None, ge=0),
    salary_max: int | None = Query(None, ge=0),
    experience_min: int = Query(0, ge=0),
    experience_max: int | None = Query(None, ge=0),
    posted_within_days: int | None = Query(None, ge=1),
    industry: str | None = None,
    job_type: str | None = None,
    roles: str | None = None,
    sources: str | None = None,
    companies: str | None = None,
    sort_by: str = Query("date"),
    include_facets: bool = True,
    limit: int = Query(20, ge=1, le=300),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    filters = JobFilters(
        q=q, locations=_csv(location), work_model=work_model, salary_min=salary_min,
        salary_max=salary_max, experience_min=experience_min, experience_max=experience_max,
        posted_within_days=posted_within_days, industry=industry, job_type=job_type,
        role_categories=_csv(roles), sources=_csv(sources), companies=_csv(companies),
    )
    return JobService(db).search(filters, sort_by, include_facets, limit, offset)


# ── Job boards ──────────────────────────────────────────────────────────────

class JobBoardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    label: str
    logo_url: str | None = None
    category: str
    is_premium: bool
    is_active: bool


boards_router = APIRouter(prefix="/api/boards", tags=["Job Boards"])


@boards_router.get("", response_model=list[JobBoardResponse])
def list_boards(active_only: bool = True, db: Session = Depends(get_db)):
    return JobService(db).list_boards(active_only)
