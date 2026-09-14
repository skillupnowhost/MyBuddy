import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ArenaCapability = Literal["TEXT", "CODE"]


class ArenaCompareRequest(BaseModel):
    capability: ArenaCapability
    prompt: str
    reference_answer: str | None = None


class ArenaComparisonResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    comparison_id: uuid.UUID
    model_id: uuid.UUID
    capability: str
    prompt: str
    response: str
    score: float | None
    latency_ms: int
    created_at: datetime


class MaxModeCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    model_id: uuid.UUID | None
    base_model: str
    response: str
    latency_ms: int
    is_judge: bool
    created_at: datetime
