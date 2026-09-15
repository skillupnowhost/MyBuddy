import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class VideoTimeline(Base):
    """MyBuddy Video Editor (spec §30-31): a non-destructive arrangement of existing Video
    clips — same role for real video that MotionProject plays for AnimationDocuments. Never
    owns pixel data itself, only the arrangement (see VideoTimelineClip); rendering a final
    MP4 is a separate, explicit export step (video_timeline_export_service), not implicit."""

    __tablename__ = "video_timelines"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    clips: Mapped[list["VideoTimelineClip"]] = relationship(
        back_populates="timeline", cascade="all, delete-orphan", order_by="VideoTimelineClip.clip_index"
    )
