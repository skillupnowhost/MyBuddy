import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class VideoTimelineClip(Base):
    """Places one Video within a VideoTimeline's ordered sequence, with an optional trim
    range. CASCADE on video_id (not SET NULL) — a clip without its source video is
    meaningless, same reasoning as MotionClip.animation_document_id."""

    __tablename__ = "video_timeline_clips"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    timeline_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("video_timelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    clip_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trim_start_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # None = play to the end of the source clip.
    trim_end_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    timeline: Mapped["VideoTimeline"] = relationship(back_populates="clips")
