import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings

settings = get_settings()

VideoGenerationStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]


class VideoGenerationCreate(BaseModel):
    prompt: str
    negative_prompt: str | None = None
    width: int = settings.video_gen_default_width
    height: int = settings.video_gen_default_height
    num_frames: int = settings.video_gen_default_num_frames
    steps: int = settings.video_gen_default_steps
    seed: int | None = None


class VideoGenerationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prompt: str
    negative_prompt: str | None
    width: int
    height: int
    num_frames: int
    fps: int
    steps: int
    seed: int | None
    status: VideoGenerationStatus
    video_id: uuid.UUID | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class VideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content_type: str
    width: int | None
    height: int | None
    duration_seconds: float | None
    size_bytes: int
    created_at: datetime
