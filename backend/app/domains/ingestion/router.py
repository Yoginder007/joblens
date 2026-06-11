import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_api_key
from app.domains.ingestion.schemas import (
    IngestRequest,
    IngestResponse,
    IngestResult,
    PortalInfo,
    ScraperWebhookPayload,
    WebhookResponse,
)
from app.domains.ingestion.scrapers import available_portals
from app.domains.ingestion.service import (
    INGEST_STATUS,
    REEMBED_STATUS,
    IngestionService,
    ingest_all,
    reembed_all,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Ingestion"])


@router.post(
    "/scraper-webhook",
    response_model=WebhookResponse,
    dependencies=[Depends(verify_api_key)],
)
def scraper_webhook(payload: ScraperWebhookPayload, db: Session = Depends(get_db)):
    inserted, updated = IngestionService(db).ingest(payload.source, payload.jobs)
    return WebhookResponse(
        status="accepted", inserted=inserted, updated=updated,
        total_received=len(payload.jobs),
    )


@router.get("/portals", response_model=list[PortalInfo])
def list_portals():
    """Directory of configured career portals (for the home page + search filter)."""
    return available_portals()


@router.post("/ingest", response_model=IngestResponse, dependencies=[Depends(verify_api_key)])
def ingest_portals(payload: IngestRequest, background: BackgroundTasks):
    """Fetch + upsert jobs for the selected companies (all configured if empty).

    ``background=true`` schedules the run and returns immediately (a full
    20-portal fetch can exceed the free-tier proxy timeout) — poll
    ``GET /api/ingest/status``. Otherwise runs synchronously and returns
    per-company results. Each company's jobs are stored with
    ``source = company`` so the UI can group by portal.
    """
    if payload.background:
        if INGEST_STATUS.get("state") == "running":
            return IngestResponse(status="already-running", results=[], total_inserted=0, total_updated=0)
        background.add_task(ingest_all, payload.companies or None)
        return IngestResponse(status="started", results=[], total_inserted=0, total_updated=0)

    out = ingest_all(payload.companies or None)
    return IngestResponse(
        status="ok",
        results=[IngestResult(**r) for r in out["results"]],
        total_inserted=out["total_inserted"],
        total_updated=out["total_updated"],
    )


@router.get("/ingest/status", dependencies=[Depends(verify_api_key)])
def ingest_status():
    return INGEST_STATUS


# ── Scheduled maintenance (driven by GitHub Actions cron on the free tier,
#    where no Celery beat process runs) ─────────────────────────────────────

@router.post("/maintenance/stale", dependencies=[Depends(verify_api_key)])
def maintenance_stale(days: int = 30):
    """Deactivate jobs not seen by any scrape in the last ``days`` days."""
    from app.workers.tasks import deactivate_stale_jobs

    return deactivate_stale_jobs(days)


@router.post("/maintenance/alerts", dependencies=[Depends(verify_api_key)])
def maintenance_alerts(frequency: str = "daily"):
    """Run all active subscriptions for the given frequency (daily/weekly)."""
    from app.workers.tasks import run_subscriptions

    return run_subscriptions(frequency)


@router.post("/reembed", status_code=202, dependencies=[Depends(verify_api_key)])
def trigger_reembed(background: BackgroundTasks):
    """Regenerate all vectors with the current embedding provider.

    Run once after switching EMBEDDING_PROVIDER (vectors from different
    providers are incompatible). Long-running, so it executes as a background
    task — poll ``GET /api/reembed/status`` for progress.
    """
    if REEMBED_STATUS.get("state") == "running":
        return {"status": "already-running", **REEMBED_STATUS}
    background.add_task(reembed_all)
    return {"status": "started"}


@router.get("/reembed/status", dependencies=[Depends(verify_api_key)])
def reembed_status():
    return REEMBED_STATUS
