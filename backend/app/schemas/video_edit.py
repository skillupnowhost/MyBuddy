import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings

settings = get_settings()

VideoEditOperation = Literal["REMOVE_BACKGROUND"]
VideoEditJobStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]


class VideoEditCreate(BaseModel):
    operation: VideoEditOperation
    source_video_id: uuid.UUID
    background_color: str = settings.video_edit_default_background_color


class VideoEditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    operation: str
    source_video_id: uuid.UUID | None
    background_color: str | None
    status: VideoEditJobStatus
    result_video_id: uuid.UUID | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
