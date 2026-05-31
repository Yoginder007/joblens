import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CandidateCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    created_at: datetime


class CandidateCreatedResponse(CandidateResponse):
    """Returned once on register/rotate — carries the raw bearer token."""

    access_token: str
