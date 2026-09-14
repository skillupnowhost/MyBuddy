import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class AgentStep(Base):
    """One tool call taken during a bounded Agent-mode turn (see agent_service.run_agent_loop).
    The final answer becomes the assistant Message itself, same convention as
    ExpertPipelineStep — these rows are the transparency trail of what the model actually did
    to get there. A turn with 0 tool calls (the model answered directly) has no rows at all."""

    __tablename__ = "agent_steps"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    assistant_reply: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_result: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
