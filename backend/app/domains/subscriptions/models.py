import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID, JSONType

# A candidate's standing intent to receive new matching jobs over time.
SUBSCRIPTION_FREQUENCIES = ("instant", "daily", "weekly")
SUBSCRIPTION_CHANNELS = ("email", "webhook")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Stored filter set, e.g. {"location": "...", "title_keyword": "...",
    # "sources": [...], "work_model": "remote"}.
    filters: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    min_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    frequency: Mapped[str] = mapped_column(String(10), default="daily")
    channel: Mapped[str] = mapped_column(String(10), default="email")
    destination: Mapped[str | None] = mapped_column(String(512))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    candidate = relationship("Candidate", back_populates="subscriptions")
    resume = relationship("Resume", back_populates="subscriptions")
    deliveries = relationship(
        "AlertDelivery", back_populates="subscription", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_subscription_active_freq", "is_active", "frequency"),
    )


class AlertDelivery(Base):
    """Record of a batch of new matches pushed to a subscriber."""

    __tablename__ = "alert_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Job UUIDs (as strings) included in this delivery — drives "already sent" dedupe.
    job_ids: Mapped[list[str]] = mapped_column(JSONType, default=list)
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    channel: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10), default="sent")  # sent|failed|skipped
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    subscription = relationship("Subscription", back_populates="deliveries")
