import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

CodeProjectStatus = Literal["UPLOADING", "EXTRACTING", "EMBEDDING", "READY", "FAILED"]
CodeExecutionStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "TIMEOUT", "CANCELLED"]


class CodeProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: CodeProjectStatus
    file_count: int
    total_size_bytes: int
    error_message: str | None
    created_at: datetime


class CodeFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    relative_path: str
    language: str | None
    size_bytes: int


class CodeFileContent(CodeFileRead):
    content: str


class CodeExecutionCreate(BaseModel):
    language: str
    source: str


class CodeExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    language: str
    status: CodeExecutionStatus
    stdout: str | None
    stderr: str | None
    exit_code: int | None
    stdout_truncated: bool
    stderr_truncated: bool
    duration_ms: int | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
