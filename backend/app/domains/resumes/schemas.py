import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ResumeUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    file_name: str
    status: str
    created_at: datetime


class ResumeDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    file_name: str
    status: str
    parsed_data: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict[str, Any] | None = None
