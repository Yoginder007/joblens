import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SubscriptionFilters(BaseModel):
    location: str | None = None
    title_keyword: str | None = None
    work_model: str | None = None
    sources: list[str] = Field(default_factory=list)


class SubscriptionCreate(BaseModel):
    resume_id: uuid.UUID
    filters: SubscriptionFilters = Field(default_factory=SubscriptionFilters)
    min_score: float = Field(default=0.0, ge=0, le=100)
    frequency: Literal["instant", "daily", "weekly"] = "daily"
    channel: Literal["email", "webhook"] = "email"
    destination: str | None = None

    @model_validator(mode="after")
    def _require_webhook_destination(self) -> "SubscriptionCreate":
        if self.channel == "webhook" and not self.destination:
            raise ValueError("destination (URL) is required when channel is 'webhook'")
        return self


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resume_id: uuid.UUID
    filters: dict[str, Any]
    min_score: float
    frequency: str
    channel: str
    destination: str | None = None
    is_active: bool
    last_run_at: datetime | None = None
    created_at: datetime
