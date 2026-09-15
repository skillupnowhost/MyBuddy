import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "system" | "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # User feedback on an assistant reply — "up" | "down" | None. Nullable/unset by default;
    # a user message is never expected to carry one, but nothing stops it at the DB level,
    # same as other columns here that are conventionally role-scoped rather than enforced so.
    feedback: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    images: Mapped[list["Image"]] = relationship(back_populates="message")
