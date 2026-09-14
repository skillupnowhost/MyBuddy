import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class MaxModeCandidate(Base):
    """One model's individual answer from a MAX-mode turn (see chat_service._max_mode_reply).
    Kept for transparency even though only the judge-synthesized reply becomes the assistant
    Message — lets a user or admin see what each model actually said. model_id is SET NULL
    (not CASCADE) so deleting/archiving a model later doesn't erase past MAX-mode history;
    base_model is stored redundantly as text so the candidate stays readable either way."""

    __tablename__ = "max_mode_candidates"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("registered_models.id", ondelete="SET NULL"), nullable=True
    )
    base_model: Mapped[str] = mapped_column(String(255), nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    is_judge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
