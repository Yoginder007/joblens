import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # SHA-256 hash of the candidate's bearer token (raw token shown once on create).
    api_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # scrypt password hash — nullable so legacy/guest candidates (created before
    # accounts existed, or via the guest flow) remain valid without a password.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    resumes = relationship(
        "Resume", back_populates="candidate", cascade="all, delete-orphan"
    )
    subscriptions = relationship(
        "Subscription", back_populates="candidate", cascade="all, delete-orphan"
    )
