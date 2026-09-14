import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class MotionProject(Base):
    """Composes several existing AnimationDocuments into one longer sequence — it never owns
    animation/shape data itself, only the arrangement (see MotionClip). The creative decisions
    (what to draw, how to animate it) already happened in Vector/Animator; this is deterministic
    composition, not a new generation surface."""

    __tablename__ = "motion_projects"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    canvas_width: Mapped[int] = mapped_column(Integer, nullable=False)
    canvas_height: Mapped[int] = mapped_column(Integer, nullable=False)
    total_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # A composed sequence is more often a one-shot playback than a single Animator clip is —
    # different default than AnimationDocument.loop (True).
    loop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    clips: Mapped[list["MotionClip"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="MotionClip.z_index"
    )
