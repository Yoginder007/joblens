import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.candidates.models import Candidate


class CandidateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, candidate_id: uuid.UUID) -> Candidate | None:
        return self.db.get(Candidate, candidate_id)

    def get_by_email(self, email: str) -> Candidate | None:
        return self.db.scalar(select(Candidate).where(Candidate.email == email))

    def get_by_token_hash(self, token_hash: str) -> Candidate | None:
        return self.db.scalar(
            select(Candidate).where(Candidate.api_token_hash == token_hash)
        )

    def add(self, candidate: Candidate) -> Candidate:
        self.db.add(candidate)
        return candidate
