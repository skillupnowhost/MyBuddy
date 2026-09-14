import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class Workspace(Base):
    """Project Workspaces (phase 9 sub-phase 5): a user-created container that groups related
    Conversations and CreativeProjects so a multi-part effort ("the sci-fi trailer project")
    has one place to see everything, instead of a flat conversation list. v1 scope, minimal
    footprint: Conversation and CreativeProject each get an optional workspace_id. CodeProject
    stays outside workspaces for now — its creation is a multipart zip upload, not a JSON
    body, and wiring workspace assignment into that endpoint is deferred rather than forced in
    for completeness. Deleting a workspace never deletes its contents (FKs are SET NULL)."""

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
