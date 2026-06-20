from typing import Literal

from pydantic import BaseModel, Field

from app.domains.jobs.schemas import JobCreate


class ScraperWebhookPayload(BaseModel):
    source: str = Field(..., min_length=1, max_length=100)
    jobs: list[JobCreate]


class WebhookResponse(BaseModel):
    status: str
    inserted: int
    updated: int
    total_received: int


class PortalInfo(BaseModel):
    company: str
    careers_url: str
    live: bool
    ats: str


class IngestRequest(BaseModel):
    """Trigger ingestion for selected companies (or all when empty)."""
    companies: list[str] = Field(default_factory=list)
    # Cost tier used when ``companies`` is empty: "free" (ATS / Adzuna / curated),
    # "paid" (Apify — weekly-throttled), or "all".
    tier: Literal["free", "paid", "all"] = "all"
    # Override the weekly paid-scrape guard. Use sparingly — paid runs cost money.
    force: bool = False
    # True → run as a background task (free-tier proxies time out long syncs);
    # poll GET /api/ingest/status for progress.
    background: bool = False


class IngestResult(BaseModel):
    company: str
    inserted: int
    updated: int
    error: str | None = None


class IngestResponse(BaseModel):
    status: str
    results: list[IngestResult]
    total_inserted: int
    total_updated: int
