"""
Subscriptions = a candidate's standing intent to receive new matching jobs.

A worker calls ``run`` on a schedule (or instantly on new ingestion); it scores
the résumé against current jobs, filters out anything already delivered, and
pushes only the *new* matches over the configured channel.
"""
import logging

import httpx
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.domains.candidates.models import Candidate
from app.domains.jobs.repository import JobFilters
from app.domains.matching.service import MatchingService
from app.domains.resumes.models import Resume
from app.domains.subscriptions.models import AlertDelivery, Subscription
from app.domains.subscriptions.repository import SubscriptionRepository
from app.domains.subscriptions.schemas import SubscriptionCreate

logger = logging.getLogger(__name__)
_ALERT_LIMIT = 50


def _filters_from(stored: dict) -> JobFilters:
    return JobFilters(
        q=stored.get("title_keyword"),
        location=stored.get("location"),
        work_model=stored.get("work_model"),
        sources=stored.get("sources") or [],
    )


class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SubscriptionRepository(db)

    def create(self, candidate: Candidate, payload: SubscriptionCreate) -> Subscription:
        resume = self.db.get(Resume, payload.resume_id)
        if resume is None:
            raise NotFoundError("Resume not found")
        if resume.candidate_id != candidate.id:
            raise ForbiddenError("Resume does not belong to this candidate")
        if resume.status != "ready":
            raise ConflictError(f"Resume is not ready (status: {resume.status})")

        destination = payload.destination
        if payload.channel == "email" and not destination:
            destination = candidate.email

        sub = Subscription(
            candidate_id=candidate.id,
            resume_id=payload.resume_id,
            filters=payload.filters.model_dump(),
            min_score=payload.min_score,
            frequency=payload.frequency,
            channel=payload.channel,
            destination=destination,
        )
        self.repo.add(sub)
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def list(self, candidate: Candidate) -> list[Subscription]:
        return self.repo.list_for_candidate(candidate.id)

    def deactivate(self, candidate: Candidate, sub_id) -> Subscription:
        sub = self.repo.get_for_candidate(sub_id, candidate.id)
        if sub is None:
            raise NotFoundError("Subscription not found")
        sub.is_active = False
        self.db.commit()
        self.db.refresh(sub)
        return sub

    # ── Worker entry point ───────────────────────────────────────────────
    def run(self, sub: Subscription) -> int:
        """Score, dedupe against past deliveries, deliver new matches. Returns count sent."""
        from datetime import datetime, timezone

        resume = sub.resume
        if resume is None or resume.status != "ready":
            return 0

        scored = MatchingService(self.db).score_candidates(
            resume, _filters_from(sub.filters or {}), _ALERT_LIMIT, float(sub.min_score)
        )
        already = self.repo.delivered_job_ids(sub.id)
        new_matches = [(job, res) for job, res in scored if str(job.id) not in already]

        sub.last_run_at = datetime.now(timezone.utc)

        if not new_matches:
            self.db.commit()
            return 0

        status, error = self._deliver(sub, new_matches)
        self.repo.add_delivery(
            AlertDelivery(
                subscription_id=sub.id,
                job_ids=[str(job.id) for job, _ in new_matches],
                match_count=len(new_matches),
                channel=sub.channel,
                status=status,
                error=error,
            )
        )
        self.db.commit()
        return len(new_matches)

    def _deliver(self, sub: Subscription, matches: list[tuple]) -> tuple[str, str | None]:
        payload = {
            "subscription_id": str(sub.id),
            "matches": [
                {
                    "job_id": str(job.id),
                    "title": job.title,
                    "company": job.company,
                    "job_url": job.job_url,
                    "match_score": round(float(res.match_score), 1),
                }
                for job, res in matches
            ],
        }
        try:
            if sub.channel == "webhook" and sub.destination:
                httpx.post(sub.destination, json=payload, timeout=10.0)
            else:
                # Email channel: integration point for an SMTP/provider client.
                logger.info(
                    "ALERT email → %s: %d new matches", sub.destination, len(matches)
                )
            return "sent", None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Alert delivery failed for %s: %s", sub.id, exc)
            return "failed", str(exc)
