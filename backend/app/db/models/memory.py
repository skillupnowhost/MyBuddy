import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class Memory(Base):
    """A durable fact/preference about a user, distinct from conversation history.

    Populated two ways: automatically (best-effort extraction after a chat reply, see
    memory_service.extract_and_save_memories) and manually (user-authored, via the API).
    Always user-editable/deletable — never a silent, unreviewable store.
    """

    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual")  # "manual" | "auto"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
