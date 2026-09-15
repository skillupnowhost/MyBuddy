import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class Video(Base):
    """A generated or uploaded video file — same role for MyBuddy Video that Image plays for
    Vision/Image gen. message_id is nullable and unused for now (no attach-video-to-chat-
    message flow exists yet). width/height/duration_seconds are nullable: a generation job
    always knows them exactly (it controlled them), but an uploaded video's are unknown
    until something actually probes the file — the backend API process deliberately has no
    video-decoding dependency (that lives only in video/'s subprocess venv, kept out of the
    lightweight main API on purpose), so upload leaves them null rather than guessing."""

    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
