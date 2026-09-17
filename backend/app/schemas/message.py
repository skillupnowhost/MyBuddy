import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.image import ImageRead


class MessageCreate(BaseModel):
    content: str
    stream: bool = True
    image_ids: list[uuid.UUID] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: Literal["system", "user", "assistant"]
    content: str
    images: list[ImageRead] = []
    feedback: Literal["up", "down"] | None = None
    created_at: datetime


class MessageFeedbackUpdate(BaseModel):
    feedback: Literal["up", "down"] | None = None
