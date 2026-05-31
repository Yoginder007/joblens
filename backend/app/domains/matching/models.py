import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID, JSONType


class JobMatch(Base):
    """A scored résumé↔job pair. One row per (resume, job), upserted on rescore."""

    __tablename__ = "job_matches"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    resume_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    match_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    hard_filter_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    semantic_similarity: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    skill_match_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    matched_skills: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType)
    reasoning: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    resume = relationship("Resume", back_populates="matches")
    job = relationship("Job", back_populates="matches")

    __table_args__ = (
        UniqueConstraint("resume_id", "job_id", name="uq_resume_job_match"),
        Index("idx_match_resume_score", "resume_id", "match_score"),
    )
