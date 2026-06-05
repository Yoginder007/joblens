from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.candidates.dependencies import CurrentCandidate
from app.domains.candidates.schemas import (
    AuthResponse,
    CandidateCreate,
    CandidateCreatedResponse,
    CandidateResponse,
    LoginRequest,
    SignupRequest,
)
from app.domains.candidates.service import CandidateService

router = APIRouter(prefix="/api/candidates", tags=["Candidates"])
auth_router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("", response_model=CandidateCreatedResponse, status_code=status.HTTP_201_CREATED)
def register_candidate(payload: CandidateCreate, db: Session = Depends(get_db)):
    """Guest registration by email — returns a one-time access token (no password)."""
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


def _auth_response(candidate, token: str) -> AuthResponse:
    return AuthResponse(
        id=candidate.id,
        email=candidate.email,
        full_name=candidate.full_name,
        created_at=candidate.created_at,
        access_token=token,
    )


@auth_router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """Create a password-backed account and return a session bearer token."""
    candidate, token = CandidateService(db).signup(payload)
    return _auth_response(candidate, token)


@auth_router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email + password; returns a fresh session bearer token."""
    candidate, token = CandidateService(db).login(payload)
    return _auth_response(candidate, token)
