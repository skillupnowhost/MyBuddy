import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MemoryCreate(BaseModel):
    content: str


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: str
    source: Literal["manual", "auto"]
    created_at: datetime
