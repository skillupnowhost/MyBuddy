import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.image import ImageRead


class MessageCreate(BaseModel):
    content: str
    stream: bool = True
    image_ids: list[uuid.UUID] = []


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: Literal["system", "user", "assistant"]
    content: str
    images: list[ImageRead] = []
    created_at: datetime
