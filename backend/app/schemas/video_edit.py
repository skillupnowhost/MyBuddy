import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.config import get_settings

settings = get_settings()

VideoEditOperation = Literal["REMOVE_BACKGROUND", "REMOVE_OBJECT", "REPLACE_ENVIRONMENT", "COLOR_GRADE", "ADD_VFX"]
VideoEditJobStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
# Fixed preset library (spec §24/§29's "cinematic/vintage/warm/cold/..." named grades) — not
# arbitrary custom-LUT support, see video/README.md. Names must match
# video/scripts/edit_video.py's _COLOR_GRADE_PRESETS exactly (duplicated, not imported: the
# backend and the video/ subprocess are separate Python environments by design).
ColorGradePreset = Literal["CINEMATIC", "VINTAGE", "WARM", "COLD", "BLACK_AND_WHITE", "NOIR", "VIVID", "MUTED"]
# Fixed particle presets (spec §17 VFX Engine) — classical simulation, not a neural VFX
# model. Names must match video/scripts/edit_video.py's _VFX_PARTICLE_PRESETS exactly, same
# duplication-not-import reasoning as ColorGradePreset.
VfxType = Literal["RAIN", "SNOW", "SPARKS"]


class VideoEditCreate(BaseModel):
    operation: VideoEditOperation
    source_video_id: uuid.UUID
    # REMOVE_BACKGROUND fields
    background_color: str = settings.video_edit_default_background_color
    # REPLACE_ENVIRONMENT fields
    background_image_id: uuid.UUID | None = None
    # REMOVE_OBJECT fields
    mask_image_id: uuid.UUID | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    steps: int = settings.image_edit_default_steps
    # COLOR_GRADE fields
    color_preset: ColorGradePreset | None = None
    # ADD_VFX fields
    vfx_type: VfxType | None = None

    @model_validator(mode="after")
    def _require_operation_specific_fields(self) -> "VideoEditCreate":
        if self.operation == "REMOVE_OBJECT" and (self.mask_image_id is None or not self.prompt):
            raise ValueError("REMOVE_OBJECT requires both 'mask_image_id' and 'prompt'")
        if self.operation == "REPLACE_ENVIRONMENT" and self.background_image_id is None:
            raise ValueError("REPLACE_ENVIRONMENT requires 'background_image_id'")
        if self.operation == "COLOR_GRADE" and self.color_preset is None:
            raise ValueError("COLOR_GRADE requires 'color_preset'")
        if self.operation == "ADD_VFX" and self.vfx_type is None:
            raise ValueError("ADD_VFX requires 'vfx_type'")
        return self


class VideoEditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    operation: str
    source_video_id: uuid.UUID | None
    background_color: str | None
    background_image_id: uuid.UUID | None
    mask_image_id: uuid.UUID | None
    prompt: str | None
    negative_prompt: str | None
    steps: int | None
    color_preset: str | None
    vfx_type: str | None
    status: VideoEditJobStatus
    result_video_id: uuid.UUID | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
