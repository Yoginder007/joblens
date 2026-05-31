import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.candidates.dependencies import CurrentCandidate
from app.domains.resumes.schemas import (
    ResumeDetailResponse,
    ResumeUploadResponse,
    TaskStatusResponse,
)
from app.domains.resumes.service import ResumeService

router = APIRouter(prefix="/api", tags=["Resumes"])


@router.post(
    "/resumes/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
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


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    from app.workers.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)
    return TaskStatusResponse(
        task_id=task_id,
        status=result.status,
        result=result.result if result.ready() and isinstance(result.result, dict) else None,
    )
