import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    created_at: datetime


class AdminStats(BaseModel):
    total_users: int
    total_conversations: int
    total_messages: int
    total_documents: int
    total_memories: int
    total_training_jobs: int


class SystemHealth(BaseModel):
    cpu_percent: float
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float
    disk_used_gb: float
    disk_total_gb: float
    disk_percent: float
    database_ok: bool
    llm_ok: bool


class RoleUpdate(BaseModel):
    role: str
