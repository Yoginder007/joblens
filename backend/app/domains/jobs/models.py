import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.core.database import Base
from app.core.types import GUID, JSONType, Vector

_DIM = get_settings().EMBEDDING_DIMENSION


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_experience_years: Mapped[int] = mapped_column(Integer, default=0)
    technical_skills: Mapped[list[str]] = mapped_column(JSONType, default=list)
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    location: Mapped[str | None] = mapped_column(String(255))
    job_url: Mapped[str | None] = mapped_column(String(512))

    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_DIM))

    work_model: Mapped[str] = mapped_column(String(20), default="on-site")
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    industry: Mapped[str | None] = mapped_column(String(100))
    company_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    company_size: Mapped[str | None] = mapped_column(String(50))
    # Nullable on purpose: only set when the source actually reports it —
    # a NULL means "unknown", never a fabricated default.
    job_type: Mapped[str | None] = mapped_column(String(30))
    # Taxonomy bucket derived from the title at ingestion (services/roles.py).
    role_category: Mapped[str | None] = mapped_column(String(40))

    posted_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # First time we saw the posting…
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # …and the most recent scrape that still returned it. Freshness filters and
    # stale deactivation key off this (refreshed on every re-ingest upsert).
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    matches = relationship(
        "JobMatch", back_populates="job", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_job_source_id"),
        Index("idx_job_active_scraped", "is_active", "scraped_at"),
        Index("idx_job_work_model", "work_model"),
        Index("idx_job_industry", "industry"),
        Index("idx_job_type", "job_type"),
        Index("idx_job_role_category", "role_category"),
        Index("idx_job_last_seen", "last_seen_at"),
    )


class JobBoard(Base):
    __tablename__ = "job_boards"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(512))
    category: Mapped[str] = mapped_column(String(50), default="general")
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
