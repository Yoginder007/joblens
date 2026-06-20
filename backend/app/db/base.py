"""
Import-all module: ensures every ORM model is registered on ``Base.metadata``
before mapper configuration / Alembic autogenerate runs.

Import this (not the individual model modules) wherever you need the full
metadata. Order doesn't matter — SQLAlchemy resolves relationships by class name.
"""
from app.core.database import Base  # noqa: F401
from app.domains.candidates.models import Candidate  # noqa: F401
from app.domains.ingestion.models import ScrapeRun  # noqa: F401
from app.domains.jobs.models import Job, JobBoard  # noqa: F401
from app.domains.matching.models import JobMatch  # noqa: F401
from app.domains.resumes.models import Resume  # noqa: F401
from app.domains.subscriptions.models import AlertDelivery, Subscription  # noqa: F401

__all__ = [
    "Base",
    "Candidate",
    "Resume",
    "Job",
    "JobBoard",
    "JobMatch",
    "Subscription",
    "AlertDelivery",
    "ScrapeRun",
]
