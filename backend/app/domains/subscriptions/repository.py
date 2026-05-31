import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.subscriptions.models import AlertDelivery, Subscription


class SubscriptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, sub_id: uuid.UUID) -> Subscription | None:
        return self.db.get(Subscription, sub_id)

    def get_for_candidate(self, sub_id: uuid.UUID, candidate_id: uuid.UUID) -> Subscription | None:
        return self.db.scalar(
            select(Subscription).where(
                Subscription.id == sub_id, Subscription.candidate_id == candidate_id
            )
        )

    def list_for_candidate(self, candidate_id: uuid.UUID) -> list[Subscription]:
        return list(
            self.db.scalars(
                select(Subscription)
                .where(Subscription.candidate_id == candidate_id)
                .order_by(Subscription.created_at.desc())
            )
        )

    def list_active(self, frequency: str | None = None) -> list[Subscription]:
        stmt = select(Subscription).where(Subscription.is_active.is_(True))
        if frequency:
            stmt = stmt.where(Subscription.frequency == frequency)
        return list(self.db.scalars(stmt))

    def delivered_job_ids(self, sub_id: uuid.UUID) -> set[str]:
        seen: set[str] = set()
        for delivery in self.db.scalars(
            select(AlertDelivery).where(AlertDelivery.subscription_id == sub_id)
        ):
            seen.update(delivery.job_ids or [])
        return seen

    def add(self, sub: Subscription) -> Subscription:
        self.db.add(sub)
        return sub

    def add_delivery(self, delivery: AlertDelivery) -> AlertDelivery:
        self.db.add(delivery)
        return delivery
