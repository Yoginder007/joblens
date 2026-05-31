from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domains.jobs.models import JobBoard
from app.domains.jobs.repository import JobFilters, JobRepository
from app.domains.jobs.schemas import JobResponse, JobSearchResponse

_SEED_BOARDS = [
    {"name": "amazon.jobs", "label": "Amazon Jobs", "category": "general", "is_premium": False},
    {"name": "linkedin", "label": "LinkedIn", "category": "premium", "is_premium": True},
    {"name": "naukri", "label": "Naukri.com", "category": "general", "is_premium": False},
    {"name": "indeed", "label": "Indeed", "category": "general", "is_premium": False},
    {"name": "wellfound", "label": "Wellfound", "category": "startup", "is_premium": False},
]


class JobService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = JobRepository(db)

    def recent(self, days: int, source: str | None, location: str | None, limit: int) -> list[JobResponse]:
        jobs = self.repo.recent(days, source, location, limit)
        return [JobResponse.model_validate(j) for j in jobs]

    def search(self, f: JobFilters, sort_by: str, include_facets: bool, limit: int, offset: int) -> JobSearchResponse:
        total = self.repo.count(f)
        jobs = self.repo.search(f, sort_by, limit, offset)
        facets = self.repo.facets(f) if include_facets else None
        return JobSearchResponse(
            total=total,
            jobs=[JobResponse.model_validate(j) for j in jobs],
            facets=facets,
        )

    def filter_options(self) -> dict[str, list[str]]:
        return self.repo.filter_options()

    def list_boards(self, active_only: bool) -> list[JobBoard]:
        if not self.db.scalar(select(func.count()).select_from(JobBoard)):
            for data in _SEED_BOARDS:
                self.db.add(JobBoard(**data))
            self.db.commit()
        stmt = select(JobBoard)
        if active_only:
            stmt = stmt.where(JobBoard.is_active.is_(True))
        return list(self.db.scalars(stmt.order_by(JobBoard.label)))
