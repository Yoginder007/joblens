from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthError
from app.core.security import extract_bearer_token, hash_token
from app.domains.candidates.models import Candidate
from app.domains.candidates.repository import CandidateRepository


def get_current_candidate(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> Candidate:
    """Resolve the owning candidate from an ``Authorization: Bearer <token>`` header."""
    token = extract_bearer_token(authorization)
    candidate = CandidateRepository(db).get_by_token_hash(hash_token(token))
    if candidate is None:
        raise AuthError("Invalid or expired access token")
    return candidate


CurrentCandidate = Annotated[Candidate, Depends(get_current_candidate)]
