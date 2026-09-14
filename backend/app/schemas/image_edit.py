import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings

settings = get_settings()

ImageEditOperation = Literal["INPAINT", "OUTPAINT", "REMOVE_BACKGROUND"]
ImageEditJobStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]


class ImageEditCreate(BaseModel):
    operation: ImageEditOperation
    source_image_id: uuid.UUID
    mask_image_id: uuid.UUID | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    steps: int = settings.image_edit_default_steps
    outpaint_top: int = 0
    outpaint_bottom: int = 0
    outpaint_left: int = 0
    outpaint_right: int = 0


class ImageEditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    operation: ImageEditOperation
    source_image_id: uuid.UUID | None
    mask_image_id: uuid.UUID | None
    prompt: str | None
    negative_prompt: str | None
    steps: int | None
    params: dict
    status: ImageEditJobStatus
    result_image_id: uuid.UUID | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
