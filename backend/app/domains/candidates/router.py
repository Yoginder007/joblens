from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.candidates.dependencies import CurrentCandidate
from app.domains.candidates.schemas import (
    CandidateCreate,
    CandidateCreatedResponse,
    CandidateResponse,
)
from app.domains.candidates.service import CandidateService

router = APIRouter(prefix="/api/candidates", tags=["Candidates"])


@router.post("", response_model=CandidateCreatedResponse, status_code=status.HTTP_201_CREATED)
def register_candidate(payload: CandidateCreate, db: Session = Depends(get_db)):
    """Register (or rotate) a candidate by email and return a one-time access token."""
    candidate, token = CandidateService(db).register_or_rotate(payload)
    return CandidateCreatedResponse(
        id=candidate.id,
        email=candidate.email,
        full_name=candidate.full_name,
        created_at=candidate.created_at,
        access_token=token,
    )


@router.get("/me", response_model=CandidateResponse)
def get_me(candidate: CurrentCandidate):
    """Return the authenticated candidate (validates the bearer token)."""
    return candidate
