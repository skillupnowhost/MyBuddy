import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class ExpertPipelineStep(Base):
    """One subtask's result from an Expert Collaboration Pipeline turn (see
    expert_pipeline_service.py: Planner -> {Reasoning|Coding|Tool} -> Verification ->
    Synthesizer). The synthesizer's final answer becomes the assistant Message itself — these
    rows are the transparency trail for the subtasks that produced it, one row per step, kept
    even after the message exists so a user/admin can see how the answer was assembled."""

    __tablename__ = "expert_pipeline_steps"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(20), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_output: Mapped[str] = mapped_column(Text, nullable=False)
    verified_output: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
