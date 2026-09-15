import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.config import get_settings

settings = get_settings()

VideoEditOperation = Literal["REMOVE_BACKGROUND", "REMOVE_OBJECT"]
VideoEditJobStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]


class VideoEditCreate(BaseModel):
    operation: VideoEditOperation
    source_video_id: uuid.UUID
    # REMOVE_BACKGROUND fields
    background_color: str = settings.video_edit_default_background_color
    # REMOVE_OBJECT fields
    mask_image_id: uuid.UUID | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    steps: int = settings.image_edit_default_steps

    @model_validator(mode="after")
    def _require_mask_and_prompt_for_object_removal(self) -> "VideoEditCreate":
        if self.operation == "REMOVE_OBJECT" and (self.mask_image_id is None or not self.prompt):
            raise ValueError("REMOVE_OBJECT requires both 'mask_image_id' and 'prompt'")
        return self


class VideoEditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    operation: str
    source_video_id: uuid.UUID | None
    background_color: str | None
    mask_image_id: uuid.UUID | None
    prompt: str | None
    negative_prompt: str | None
    steps: int | None
    status: VideoEditJobStatus
    result_video_id: uuid.UUID | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
