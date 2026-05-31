import hashlib
import logging
import os
import uuid

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.domains.resumes.models import Resume
from app.domains.resumes.repository import ResumeRepository

logger = logging.getLogger(__name__)
_CHUNK = 1024 * 1024


class ResumeService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ResumeRepository(db)

    async def upload(self, candidate_id: uuid.UUID, file: UploadFile) -> Resume:
        settings = get_settings()

        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise ValidationError("Only PDF files are supported")

        # Stream to disk while enforcing the size cap (no full buffer in RAM).
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        stored_name = f"{uuid.uuid4()}.pdf"
        file_path = os.path.join(settings.UPLOAD_DIR, stored_name)
        hasher = hashlib.sha256()
        total = 0
        try:
            with open(file_path, "wb") as out:
                while chunk := await file.read(_CHUNK):
                    total += len(chunk)
                    if total > settings.max_file_bytes:
                        raise ValidationError(
                            f"File exceeds {settings.MAX_FILE_SIZE_MB} MB"
                        )
                    hasher.update(chunk)
                    out.write(chunk)
        except ValidationError:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise

        if total == 0:
            os.remove(file_path)
            raise ValidationError("Uploaded file is empty")

        resume = Resume(
            candidate_id=candidate_id,
            file_name=file.filename,
            file_path=file_path,
            content_hash=hasher.hexdigest(),
            status="pending",
        )
        self.repo.add(resume)
        self.db.commit()
        self.db.refresh(resume)

        from app.workers.tasks import process_resume

        process_resume.delay(str(resume.id))
        logger.info("Résumé %s queued for processing", resume.id)
        return resume

    def get_owned(self, resume_id: uuid.UUID, candidate_id: uuid.UUID) -> Resume:
        resume = self.repo.get_for_candidate(resume_id, candidate_id)
        if resume is None:
            raise NotFoundError("Resume not found")
        return resume
