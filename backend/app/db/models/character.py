import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class Character(Base):
    """CharacterIdentitySystem (video/CG/VFX spec §8), minimal-footprint v1 — same treatment
    as BrandKit: plain manual metadata, no LLM generation, no LoRA/embedding/face-consistency
    mechanism (that's a real ML system this project has no GPU to build or run). Consistency
    today means exactly one thing: character_service.character_guidance() prepends this
    character's description to a generation prompt (Storyboard today; Vector/Image/Video
    wherever a future caller passes character_ids through) — the same honest, prompt-
    injection-only consistency approach BrandKit already established for brand identity."""

    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_image_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
