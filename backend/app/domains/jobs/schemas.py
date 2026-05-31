import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    company: str
    description: str
    required_experience_years: int
    technical_skills: list[str] | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    location: str | None = None
    job_url: str | None = None
    source: str
    source_id: str
    posted_date: datetime | None = None
    scraped_at: datetime | None = None
    is_active: bool
    is_remote: bool
    work_model: str | None = None
    industry: str | None = None
    company_rating: Decimal | None = None
    company_size: str | None = None
    job_type: str | None = None


class JobCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    company: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    required_experience_years: int = Field(default=0, ge=0)
    technical_skills: list[str] = Field(default_factory=list)
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    location: str | None = None
    job_url: str | None = None
    source_id: str = Field(..., min_length=1)
    work_model: str | None = None
    industry: str | None = None
    company_rating: Decimal | None = None
    company_size: str | None = None
    job_type: str | None = None
    is_remote: bool = False


class FacetCounts(BaseModel):
    work_model: dict[str, int] = {}
    experience_ranges: dict[str, int] = {}
    industries: dict[str, int] = {}
    job_types: dict[str, int] = {}
    posted_within: dict[str, int] = {}
    sources: dict[str, int] = {}


class JobSearchResponse(BaseModel):
    total: int
    jobs: list[JobResponse]
    facets: FacetCounts | None = None
