import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID

# Runs as a separate OS process (see video/scripts/export_timeline.py), never inside the API
# process — same pattern as VideoGenerationJob/VideoEditJob. Pure frame I/O (trim +
# concatenate via imageio), no ML model at all — CPU-fast like REMOVE_BACKGROUND/COLOR_GRADE,
# not GPU-heavy.
VIDEO_TIMELINE_EXPORT_JOB_STATUSES = ("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED")


class VideoTimelineExportJob(Base):
    __tablename__ = "video_timeline_export_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timeline_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("video_timelines.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    result_video_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("videos.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
