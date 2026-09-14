import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings

settings = get_settings()

ImageGenerationStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]


class ImageGenerationCreate(BaseModel):
    prompt: str
    negative_prompt: str | None = None
    width: int = settings.image_gen_default_width
    height: int = settings.image_gen_default_height
    steps: int = settings.image_gen_default_steps
    seed: int | None = None


class ImageGenerationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prompt: str
    negative_prompt: str | None
    width: int
    height: int
    steps: int
    seed: int | None
    status: ImageGenerationStatus
    image_id: uuid.UUID | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
