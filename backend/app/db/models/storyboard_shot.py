import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class StoryboardShot(Base):
    """One shot in a Storyboard — fields match the spec's per-shot list (§7): shot_id (this
    row's id), scene_id, duration, camera, lens, composition, characters, action,
    environment, lighting, dialogue, sound, VFX, generation_prompt. `reference_image` from
    the spec is deliberately not a column yet — no shot-level image generation exists in
    this v1, so there's nothing to reference; add it once MyBuddy Video/Image actually wires
    into a shot."""

    __tablename__ = "storyboard_shots"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    storyboard_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("storyboards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    scene_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    camera: Mapped[str] = mapped_column(String(255), nullable=False)
    lens: Mapped[str | None] = mapped_column(String(100), nullable=True)
    composition: Mapped[str | None] = mapped_column(String(255), nullable=True)
    characters: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    environment: Mapped[str] = mapped_column(Text, nullable=False)
    lighting: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dialogue: Mapped[str | None] = mapped_column(Text, nullable=True)
    sound: Mapped[str | None] = mapped_column(Text, nullable=True)
    vfx: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    storyboard: Mapped["Storyboard"] = relationship(back_populates="shots")
