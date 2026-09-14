import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorldBibleCreate(BaseModel):
    name: str
    setting_description: str | None = None
    atmosphere: str | None = None
    visual_style: str | None = None
    color_palette: str | None = None
    rules: str | None = None


class WorldBiblePatch(BaseModel):
    name: str | None = None
    setting_description: str | None = None
    atmosphere: str | None = None
    visual_style: str | None = None
    color_palette: str | None = None
    rules: str | None = None


class WorldBibleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    setting_description: str | None
    atmosphere: str | None
    visual_style: str | None
    color_palette: str | None
    rules: str | None
    created_at: datetime
    updated_at: datetime
