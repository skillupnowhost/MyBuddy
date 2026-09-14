import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID

# Runs as a separate OS process (see imagegen/scripts/edit_image.py), never inside the API
# process — same pattern as ImageGenerationJob.
IMAGE_EDIT_OPERATIONS = ("INPAINT", "OUTPAINT", "REMOVE_BACKGROUND")
IMAGE_EDIT_JOB_STATUSES = ("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED")


class ImageEditJob(Base):
    __tablename__ = "image_edit_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    source_image_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    mask_image_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Operation-specific knobs (outpaint top/bottom/left/right padding); empty for
    # inpaint/remove_background — same convention as TrainingJob.config.
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    result_image_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
