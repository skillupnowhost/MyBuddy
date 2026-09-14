import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.conversation import ConversationRead
from app.schemas.creative import CreativeProjectRead


class WorkspaceCreate(BaseModel):
    name: str
    description: str | None = None


class WorkspacePatch(BaseModel):
    name: str | None = None
    description: str | None = None


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class WorkspaceDetail(WorkspaceRead):
    conversations: list[ConversationRead] = []
    creative_projects: list[CreativeProjectRead] = []
