import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MessageCreate(BaseModel):
    content: str
    stream: bool = True


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: Literal["system", "user", "assistant"]
    content: str
    created_at: datetime
