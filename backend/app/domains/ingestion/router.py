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
from app.domains.ingestion.scrapers import (
    CAREER_PAGES,
    available_portals,
    run_scraper_for_company,
)
from app.domains.ingestion.service import (
    REEMBED_STATUS,
    IngestionService,
    reembed_all,
)
from app.domains.jobs.schemas import JobCreate

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
def ingest_portals(payload: IngestRequest, db: Session = Depends(get_db)):
    """Fetch + upsert jobs for the selected companies (all configured if empty).

    Runs synchronously so the caller (seed script / admin) gets per-company
    results. Each company's jobs are stored with ``source = company`` so the UI
    can group by portal.
    """
    companies = payload.companies or list(CAREER_PAGES.keys())
    results: list[IngestResult] = []
    svc = IngestionService(db)
    for company in companies:
        try:
            raw = run_scraper_for_company(company)
            jobs = [JobCreate(**data) for data in raw]
            inserted, updated = svc.ingest(company, jobs)
            results.append(IngestResult(company=company, inserted=inserted, updated=updated))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ingest failed for %s", company)
            results.append(IngestResult(company=company, inserted=0, updated=0, error=str(exc)[:200]))

    return IngestResponse(
        status="ok",
        results=results,
        total_inserted=sum(r.inserted for r in results),
        total_updated=sum(r.updated for r in results),
    )


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
