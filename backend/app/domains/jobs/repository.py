"""
Job data access. All query logic (scalar filters, pgvector ANN, SQL-side facet
aggregation) lives here so services stay thin and the DB does the heavy lifting.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app.domains.jobs.models import Job
from app.domains.jobs.schemas import FacetCounts

# Country → substrings that appear in job locations for that country. Lets a
# user pick a country as a "location" and get every job there. Keyed lowercase.
COUNTRY_ALIASES: dict[str, list[str]] = {
    "india": [", ind", ", india", "india", "bengaluru", "bangalore", "hyderabad",
              "pune", "chennai", "mumbai", "delhi", "noida", "gurugram", "gurgaon", "kolkata"],
    "united states": [", usa", ", united states", "california", "washington",
                      "new york", "texas", "massachusetts"],
    "usa": [", usa", ", united states"],
    "united kingdom": [", uk", ", gbr", "london", "england"],
    "uk": [", uk", ", gbr", "london"],
    "canada": [", can", ", canada", "toronto", "vancouver", "calgary"],
    "germany": ["germany", "berlin"],
    "remote": ["remote"],
}

# Countries offered in the location dropdown (prefixed so the UI can group them).
COUNTRY_OPTIONS = ["India", "United States", "United Kingdom", "Canada", "Germany", "Remote"]


@dataclass
class JobFilters:
    q: str | None = None
    location: str | None = None
    locations: list[str] = field(default_factory=list)  # multi-location (OR)
    work_model: str | None = None
    location_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    experience_min: int = 0
    experience_max: int | None = None
    posted_within_days: int | None = None
    industry: str | None = None
    job_type: str | None = None
    sources: list[str] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self.db.get(Job, job_id)

    def get_by_source(self, source: str, source_id: str) -> Job | None:
        return self.db.scalar(
            select(Job).where(Job.source == source, Job.source_id == source_id)
        )

    # ── Filtering ──────────────────────────────────────────────────────────
    def _apply(self, stmt: Select, f: JobFilters) -> Select:
        stmt = stmt.where(Job.is_active.is_(True))
        if f.q:
            like = f"%{f.q.lower()}%"
            stmt = stmt.where(
                or_(func.lower(Job.title).like(like), func.lower(Job.description).like(like))
            )
        # Location: single substring OR any-of a multi-location list (OR semantics
        # so "show jobs in Bangalore OR Pune OR Remote" works). A country name
        # expands to all its location aliases so "India" matches "…, IND" etc.
        locs = list(f.locations) if f.locations else ([f.location] if f.location else [])
        locs = [l.strip() for l in locs if l and l.strip()]
        if locs:
            patterns: list[str] = []
            for l in locs:
                patterns.extend(COUNTRY_ALIASES.get(l.lower(), [l]))
            stmt = stmt.where(or_(*[Job.location.ilike(f"%{p}%") for p in patterns]))
        if f.work_model:
            stmt = stmt.where(func.lower(Job.work_model) == f.work_model.lower())
        if f.location_type:
            lt = f.location_type.lower()
            if lt == "remote":
                stmt = stmt.where(or_(Job.is_remote.is_(True), func.lower(Job.work_model) == "remote"))
            else:
                stmt = stmt.where(func.lower(Job.work_model) == lt)
        if f.salary_min is not None:
            stmt = stmt.where(or_(Job.salary_max >= f.salary_min, Job.salary_max.is_(None)))
        if f.salary_max is not None:
            stmt = stmt.where(or_(Job.salary_min <= f.salary_max, Job.salary_min.is_(None)))
        if f.experience_min > 0:
            stmt = stmt.where(Job.required_experience_years >= f.experience_min)
        if f.experience_max is not None and f.experience_max > 0:
            stmt = stmt.where(Job.required_experience_years <= f.experience_max)
        if f.posted_within_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=f.posted_within_days)
            stmt = stmt.where(Job.scraped_at >= cutoff)
        if f.industry:
            stmt = stmt.where(func.lower(Job.industry) == f.industry.lower())
        if f.job_type:
            stmt = stmt.where(func.lower(Job.job_type) == f.job_type.lower())
        if f.sources:
            stmt = stmt.where(func.lower(Job.source).in_([s.lower() for s in f.sources]))
        if f.companies:
            stmt = stmt.where(Job.company.in_(f.companies))
        return stmt

    def count(self, f: JobFilters) -> int:
        stmt = self._apply(select(func.count()).select_from(Job), f)
        return int(self.db.scalar(stmt) or 0)

    def search(self, f: JobFilters, sort_by: str, limit: int, offset: int) -> list[Job]:
        stmt = self._apply(select(Job), f)
        if sort_by == "salary":
            stmt = stmt.order_by(Job.salary_max.desc().nullslast())
        elif sort_by == "relevance" and f.q:
            stmt = stmt.order_by(func.length(Job.title).asc(), Job.scraped_at.desc())
        else:
            stmt = stmt.order_by(Job.scraped_at.desc().nullslast())
        return list(self.db.scalars(stmt.offset(offset).limit(limit)))

    def recent(self, days: int, source: str | None, location: str | None, limit: int) -> list[Job]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = select(Job).where(Job.is_active.is_(True), Job.scraped_at >= cutoff)
        if source:
            stmt = stmt.where(Job.source.ilike(f"%{source}%"))
        if location:
            stmt = stmt.where(Job.location.ilike(f"%{location}%"))
        stmt = stmt.order_by(Job.scraped_at.desc().nullslast()).limit(limit)
        return list(self.db.scalars(stmt))

    def eligible(self, candidate_exp: int, f: JobFilters, limit: int) -> list[Job]:
        """Jobs the candidate qualifies for (required_experience <= candidate_exp).

        Ordered by recency BEFORE limiting so the candidate pool is deterministic
        and meaningful (newest eligible jobs) — without an ORDER BY the DB would
        return an arbitrary subset, which the caller then ranks by score.
        """
        stmt = self._apply(select(Job), f)
        stmt = stmt.where(Job.required_experience_years <= candidate_exp)
        stmt = stmt.order_by(Job.scraped_at.desc().nullslast())
        return list(self.db.scalars(stmt.limit(limit)))

    def nearest(self, embedding, candidate_exp: int, f: JobFilters, limit: int) -> list[tuple[Job, float]]:
        """Nearest jobs the candidate qualifies for, as (job, cosine_distance).

        Postgres uses a pgvector ANN index; SQLite scores in Python (dev only).
        """
        if self.db.bind.dialect.name == "postgresql":
            dist = Job.embedding.cosine_distance(embedding).label("distance")
            stmt = self._apply(select(Job, dist), f)
            stmt = stmt.where(
                Job.embedding.isnot(None),
                Job.required_experience_years <= candidate_exp,
            ).order_by(dist).limit(limit)
            return [(row[0], float(row[1])) for row in self.db.execute(stmt).all()]

        from app.services.embedding import cosine_similarity

        stmt = self._apply(select(Job), f).where(
            Job.embedding.isnot(None),
            Job.required_experience_years <= candidate_exp,
        )
        scored = [
            (job, 1.0 - cosine_similarity(list(embedding), list(job.embedding)))
            for job in self.db.scalars(stmt)
        ]
        scored.sort(key=lambda x: x[1])
        return scored[:limit]

    # ── Facets (aggregated in SQL, not in Python) ────────────────────────────
    def facets(self, f: JobFilters) -> FacetCounts:
        def grouped(column) -> dict[str, int]:
            stmt = self._apply(select(column, func.count()).group_by(column), f)
            return {str(k): int(c) for k, c in self.db.execute(stmt).all() if k is not None}

        exp_col = func.coalesce(Job.required_experience_years, 0)
        bucket = case(
            (exp_col <= 2, "0-2 years"),
            (exp_col <= 5, "3-5 years"),
            (exp_col <= 8, "6-8 years"),
            else_="9+ years",
        )
        exp_stmt = self._apply(select(bucket.label("b"), func.count()).group_by("b"), f)
        exp_ranges = {str(k): int(c) for k, c in self.db.execute(exp_stmt).all()}

        # Single pass: one conditional SUM per bucket instead of 5 COUNT queries.
        now = datetime.now(timezone.utc)
        buckets = (("24h", 1), ("3d", 3), ("7d", 7), ("14d", 14), ("30d", 30))
        cols = [
            func.sum(case((Job.scraped_at >= now - timedelta(days=d), 1), else_=0)).label(label)
            for label, d in buckets
        ]
        row = self.db.execute(self._apply(select(*cols), f)).one()
        posted = {label: int(getattr(row, label) or 0) for label, _ in buckets}

        return FacetCounts(
            work_model=grouped(Job.work_model),
            experience_ranges=exp_ranges,
            industries=grouped(Job.industry),
            job_types=grouped(Job.job_type),
            posted_within=posted,
            sources=grouped(Job.source),
        )

    # ── Distinct filter options (for UI dropdowns) ───────────────────────────
    def filter_options(self) -> dict[str, list[str]]:
        """Distinct, non-null values across active jobs — feeds the home dropdowns
        so users pick only values that actually return results."""
        def distinct(column, limit: int = 200) -> list[str]:
            stmt = (
                select(column)
                .where(Job.is_active.is_(True), column.isnot(None), column != "")
                .distinct()
                .order_by(column)
                .limit(limit)
            )
            return [str(v) for v in self.db.scalars(stmt) if v]

        # Offer countries first in the location list (so users can pick a whole
        # country), followed by the specific cities present in the data.
        return {
            "locations": distinct(Job.location),
            "countries": list(COUNTRY_OPTIONS),
            "industries": distinct(Job.industry),
            "titles": distinct(Job.title),
            "companies": distinct(Job.company),
            "sources": distinct(Job.source),
            "work_models": distinct(Job.work_model),
            "job_types": distinct(Job.job_type),
        }

    # ── Ingestion (race-safe upsert) ─────────────────────────────────────────
    def add(self, job: Job) -> Job:
        self.db.add(job)
        return job
