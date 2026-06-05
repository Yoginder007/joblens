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


# ── Account auth (email + password) ──────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class AuthResponse(CandidateResponse):
    """Returned on signup/login — carries a fresh bearer token for the session."""

    access_token: str
