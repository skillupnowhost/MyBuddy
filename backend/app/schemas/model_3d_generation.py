import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.config import get_settings

settings = get_settings()

Model3DGenerationStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]


class Model3DGenerationCreate(BaseModel):
    prompt: str | None = None
    source_image_id: uuid.UUID | None = None
    steps: int = settings.cg3d_default_steps
    guidance_scale: float = settings.cg3d_default_guidance_scale
    seed: int | None = None

    @model_validator(mode="after")
    def _require_prompt_or_image(self) -> "Model3DGenerationCreate":
        if not self.prompt and self.source_image_id is None:
            raise ValueError("either 'prompt' (text-to-3D) or 'source_image_id' (image-to-3D) is required")
        return self


class Model3DGenerationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prompt: str | None
    source_image_id: uuid.UUID | None
    steps: int
    guidance_scale: float
    seed: int | None
    status: Model3DGenerationStatus
    model_3d_id: uuid.UUID | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class Model3DRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    format: str
    size_bytes: int
    created_at: datetime
