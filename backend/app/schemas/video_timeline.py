import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VideoTimelineCreate(BaseModel):
    title: str = "Untitled timeline"


class VideoTimelineClipCreate(BaseModel):
    video_id: uuid.UUID
    trim_start_seconds: float = Field(default=0.0, ge=0)
    trim_end_seconds: float | None = Field(default=None, gt=0)


class VideoTimelineClipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    clip_index: int
    trim_start_seconds: float
    trim_end_seconds: float | None
    created_at: datetime


class VideoTimelineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class VideoTimelineDetail(VideoTimelineRead):
    clips: list[VideoTimelineClipRead] = []


VideoTimelineExportStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]


class VideoTimelineExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timeline_id: uuid.UUID | None
    status: VideoTimelineExportStatus
    result_video_id: uuid.UUID | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
