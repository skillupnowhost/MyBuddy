import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID

ANIMATION_EASINGS = ("LINEAR", "EASE_IN", "EASE_OUT", "EASE_IN_OUT")


class AnimationDocument(Base):
    """Animates an existing VectorDocument's objects over time — it never owns its own shape
    data, only a timeline of keyframes targeting that document's objects. CASCADE (not SET
    NULL like e.g. ImageEditJob's image refs) because an animation without its target scene
    is meaningless."""

    __tablename__ = "animation_documents"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vector_document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("vector_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    frame_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    loop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    keyframes: Mapped[list["AnimationKeyframe"]] = relationship(
        back_populates="animation", cascade="all, delete-orphan", order_by="AnimationKeyframe.time_ms"
    )
