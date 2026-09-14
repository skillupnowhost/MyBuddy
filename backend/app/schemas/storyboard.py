import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StoryboardGenerateRequest(BaseModel):
    title: str | None = None
    script: str


class StoryboardShotCreate(BaseModel):
    scene_id: str | None = None
    duration_seconds: float = Field(gt=0)
    camera: str
    lens: str | None = None
    composition: str | None = None
    characters: list[str] = []
    action: str
    environment: str
    lighting: str | None = None
    dialogue: str | None = None
    sound: str | None = None
    vfx: str | None = None
    generation_prompt: str


class StoryboardShotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shot_index: int
    scene_id: str | None
    duration_seconds: float
    camera: str
    lens: str | None
    composition: str | None
    characters: list[str]
    action: str
    environment: str
    lighting: str | None
    dialogue: str | None
    sound: str | None
    vfx: str | None
    generation_prompt: str
    created_at: datetime


class StoryboardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    script: str
    created_at: datetime
    updated_at: datetime


class StoryboardDetail(StoryboardRead):
    shots: list[StoryboardShotRead] = []
