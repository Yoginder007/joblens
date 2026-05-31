import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.candidates.dependencies import CurrentCandidate
from app.domains.subscriptions.schemas import SubscriptionCreate, SubscriptionResponse
from app.domains.subscriptions.service import SubscriptionService

router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions"])


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
    candidate: CurrentCandidate,
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
):
    """Subscribe a résumé to ongoing job alerts matching the given filters."""
    return SubscriptionService(db).create(candidate, payload)


@router.get("", response_model=list[SubscriptionResponse])
def list_subscriptions(candidate: CurrentCandidate, db: Session = Depends(get_db)):
    return SubscriptionService(db).list(candidate)


@router.delete("/{subscription_id}", response_model=SubscriptionResponse)
def deactivate_subscription(
    candidate: CurrentCandidate,
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    return SubscriptionService(db).deactivate(candidate, subscription_id)
