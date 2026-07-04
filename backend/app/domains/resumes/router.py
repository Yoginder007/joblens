import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthError
from app.core.ratelimit import upload_limiter
from app.core.security import hash_token
from app.domains.candidates.dependencies import CurrentCandidate
from app.domains.candidates.repository import CandidateRepository
from app.domains.resumes.models import Resume
from app.domains.resumes.schemas import (
    ResumeDetailResponse,
    ResumeUploadResponse,
    TaskStatusResponse,
)
from app.domains.resumes.service import ResumeService

router = APIRouter(prefix="/api", tags=["Resumes"])

# Terminal résumé states — the SSE stream closes once one is reached.
_TERMINAL = ("ready", "failed")


@router.post(
    "/resumes/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(upload_limiter)],
)
async def upload_resume(
    candidate: CurrentCandidate,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a PDF résumé for the authenticated candidate; processed async."""
    return await ResumeService(db).upload(candidate.id, file)


@router.get("/resumes/{resume_id}", response_model=ResumeDetailResponse)
def get_resume(resume_id: uuid.UUID, candidate: CurrentCandidate, db: Session = Depends(get_db)):
    return ResumeService(db).get_owned(resume_id, candidate.id)


@router.get("/resumes/{resume_id}/stream")
async def stream_resume_status(
    resume_id: uuid.UUID,
    token: str = Query(..., description="Bearer access token (EventSource cannot set headers)"),
):
    """Server-Sent Events stream of a résumé's processing status until it reaches
    a terminal state (ready/failed) — replaces client-side 1s polling.

    Auth rides as a ``token`` query param because the browser EventSource API
    can't send an Authorization header. Each poll uses a fresh short-lived
    session so it sees the worker's committed status updates.

    Async on purpose: a sync generator would pin a threadpool thread per
    watcher for up to 3 minutes — a few dozen concurrent uploads would starve
    every sync endpoint sharing that pool. Here only the ~ms DB reads borrow a
    thread; the 1 s waits cost nothing.
    """
    from app.core.database import SessionLocal

    def _auth() -> None:
        db = SessionLocal()
        try:
            candidate = CandidateRepository(db).get_by_token_hash(hash_token(token))
            if candidate is None:
                raise AuthError("Invalid or expired access token")
            ResumeService(db).get_owned(resume_id, candidate.id)  # raises 404 if not owned
        finally:
            db.close()

    def _current_status() -> str:
        s = SessionLocal()
        try:
            resume = s.get(Resume, resume_id)
            return resume.status if resume else "failed"
        finally:
            s.close()

    # Auth + ownership up-front (short-lived session, released before streaming).
    await run_in_threadpool(_auth)

    async def event_stream():
        last = None
        for _ in range(180):  # ~3 min safety cap
            current = await run_in_threadpool(_current_status)
            if current != last:
                yield f"data: {json.dumps({'status': current})}\n\n"
                last = current
            if current in _TERMINAL:
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str, candidate: CurrentCandidate):
    from app.workers.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)
    return TaskStatusResponse(
        task_id=task_id,
        status=result.status,
        result=result.result if result.ready() and isinstance(result.result, dict) else None,
    )
