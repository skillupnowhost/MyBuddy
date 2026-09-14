import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CharacterCreate(BaseModel):
    name: str
    appearance: str | None = None
    personality: str | None = None
    voice_description: str | None = None
    reference_image_id: uuid.UUID | None = None


class CharacterPatch(BaseModel):
    name: str | None = None
    appearance: str | None = None
    personality: str | None = None
    voice_description: str | None = None
    reference_image_id: uuid.UUID | None = None


class CharacterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    appearance: str | None
    personality: str | None
    voice_description: str | None
    reference_image_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
