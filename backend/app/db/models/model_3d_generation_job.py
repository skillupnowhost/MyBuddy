import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID

# Runs as a separate OS process (see cg3d/scripts/generate.py), never inside the API process
# — same pattern as ImageGenerationJob/VideoGenerationJob.
MODEL_3D_GENERATION_JOB_STATUSES = ("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED")


class Model3DGenerationJob(Base):
    __tablename__ = "model_3d_generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # TEXT->3D when prompt is set and source_image_id is null; IMAGE->3D when source_image_id
    # is set (prompt then optional/unused) — same "one job type, mode implied by which input
    # is present" shape as ImageEditJob.
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_image_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    steps: Mapped[int] = mapped_column(Integer, nullable=False)
    guidance_scale: Mapped[float] = mapped_column(Float, nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    model_3d_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("models_3d.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
