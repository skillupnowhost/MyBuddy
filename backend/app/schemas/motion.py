import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MotionClipCreate(BaseModel):
    animation_document_id: uuid.UUID
    start_offset_ms: int = 0
    x_offset: int = 0
    y_offset: int = 0
    z_index: int = 0


class MotionClipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    animation_document_id: uuid.UUID
    start_offset_ms: int
    x_offset: int
    y_offset: int
    z_index: int
    created_at: datetime


class MotionClipPatch(BaseModel):
    start_offset_ms: int | None = None
    x_offset: int | None = None
    y_offset: int | None = None
    z_index: int | None = None


class MotionProjectCreate(BaseModel):
    title: str
    canvas_width: int
    canvas_height: int
    total_duration_ms: int
    loop: bool = False


class MotionProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    canvas_width: int
    canvas_height: int
    total_duration_ms: int
    loop: bool
    clips: list[MotionClipRead] = []
    created_at: datetime
    updated_at: datetime
