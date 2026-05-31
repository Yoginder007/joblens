import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.core.database import Base
from app.core.types import GUID, JSONType, Vector

_DIM = get_settings().EMBEDDING_DIMENSION

# Lifecycle: pending → processing → embedding → ready | failed
RESUME_STATUSES = ("pending", "processing", "embedding", "ready", "failed")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    raw_text: Mapped[str | None] = mapped_column(Text)
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_DIM))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    candidate = relationship("Candidate", back_populates="resumes")
    matches = relationship(
        "JobMatch", back_populates="resume", cascade="all, delete-orphan"
    )
    subscriptions = relationship("Subscription", back_populates="resume")
