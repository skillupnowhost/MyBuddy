import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.message import MessageRead


class ConversationCreate(BaseModel):
    title: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    rag_enabled: bool = False
    tools_enabled: bool = True
    max_mode_enabled: bool = False
    expert_pipeline_enabled: bool = False
    agent_mode_enabled: bool = False
    code_project_id: uuid.UUID | None = None
    workspace_id: uuid.UUID | None = None


class ConversationUpdate(BaseModel):
    title: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    rag_enabled: bool | None = None
    tools_enabled: bool | None = None
    max_mode_enabled: bool | None = None
    expert_pipeline_enabled: bool | None = None
    agent_mode_enabled: bool | None = None
    code_project_id: uuid.UUID | None = None
    workspace_id: uuid.UUID | None = None


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    system_prompt: str | None
    model: str | None
    rag_enabled: bool
    tools_enabled: bool
    max_mode_enabled: bool
    expert_pipeline_enabled: bool
    agent_mode_enabled: bool
    code_project_id: uuid.UUID | None
    workspace_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[MessageRead] = []
