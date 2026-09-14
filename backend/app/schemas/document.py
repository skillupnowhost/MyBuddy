import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DocumentStatus = Literal["UPLOADING", "PROCESSING", "EMBEDDING", "READY", "FAILED"]


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    error_message: str | None
    created_at: datetime


class RetrievedChunk(BaseModel):
    content: str
    page_number: int | None
    document_filename: str
