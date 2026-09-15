import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID

# Runs as a separate OS process (see video/scripts/edit_video.py), never inside the API
# process — same pattern as VideoGenerationJob. REMOVE_BACKGROUND uses rembg (CPU-fast, no
# GPU dependency) rather than diffusion, so it's the one video-track operation that actually
# completes on this project's dev hardware. REMOVE_OBJECT reuses the same SD inpainting
# pipeline as ImageEditJob's INPAINT, applied frame-by-frame with one static mask — same
# GPU/CPU-hardware caveat as generation (spec §21 AI Object Removal; per-frame *tracking* of
# a moving object/mask is explicitly out of scope for v1, see video/README.md).
VIDEO_EDIT_OPERATIONS = ("REMOVE_BACKGROUND", "REMOVE_OBJECT")
VIDEO_EDIT_JOB_STATUSES = ("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED")


class VideoEditJob(Base):
    __tablename__ = "video_edit_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    source_video_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("videos.id", ondelete="SET NULL"), nullable=True
    )
    background_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # REMOVE_OBJECT only: mask convention matches ImageEditJob's INPAINT (white = remove/
    # regenerate, black = keep), applied identically to every frame.
    mask_image_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    result_video_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("videos.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
