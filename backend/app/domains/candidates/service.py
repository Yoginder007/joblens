from sqlalchemy.orm import Session

from app.core.security import generate_token, hash_token
from app.domains.candidates.models import Candidate
from app.domains.candidates.repository import CandidateRepository
from app.domains.candidates.schemas import CandidateCreate


class CandidateService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CandidateRepository(db)

    def register_or_rotate(self, payload: CandidateCreate) -> tuple[Candidate, str]:
        """
        Upsert by email and (re)issue a bearer token.

        Returns the candidate plus the raw token (shown to the client once).
        Re-registering the same email rotates the token, so the latest caller
        owns the candidate's résumés.
        """
        raw_token = generate_token()
        token_hash = hash_token(raw_token)

        candidate = self.repo.get_by_email(payload.email)
        if candidate is None:
            candidate = Candidate(
                email=payload.email,
                full_name=payload.full_name,
                api_token_hash=token_hash,
            )
            self.repo.add(candidate)
        else:
            candidate.full_name = payload.full_name
            candidate.api_token_hash = token_hash

        self.db.commit()
        self.db.refresh(candidate)
        return candidate, raw_token
