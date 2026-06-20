import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID, JSONType


class ScrapeRun(Base):
    """A record of one cost-tier ingest run.

    Used to (a) throttle paid (Apify) scraping to a weekly cadence — the guard in
    ``ingest_all`` skips paid sources when the most recent paid run is < 7 days
    old — and (b) give cost visibility via the new-vs-duplicate counts.
    """

    __tablename__ = "scrape_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tier: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # free | paid
    companies: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    returned: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
