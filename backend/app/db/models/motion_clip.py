import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class MotionClip(Base):
    """Places one AnimationDocument within a MotionProject's shared timeline/canvas. CASCADE
    on animation_document_id (not SET NULL) — a clip without its animation is meaningless,
    same reasoning as AnimationDocument.vector_document_id."""

    __tablename__ = "motion_clips"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    motion_project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("motion_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    animation_document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("animation_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_offset_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    x_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    y_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    z_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["MotionProject"] = relationship(back_populates="clips")
