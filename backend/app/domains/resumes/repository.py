import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.resumes.models import Resume


class ResumeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, resume_id: uuid.UUID) -> Resume | None:
        return self.db.get(Resume, resume_id)

    def get_for_candidate(self, resume_id: uuid.UUID, candidate_id: uuid.UUID) -> Resume | None:
        return self.db.scalar(
            select(Resume).where(
                Resume.id == resume_id, Resume.candidate_id == candidate_id
            )
        )

    def add(self, resume: Resume) -> Resume:
        self.db.add(resume)
        return resume
