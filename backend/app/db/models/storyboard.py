import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class Storyboard(Base):
    """StoryboardGenerator (video/CG/VFX spec §7): a script turned into a shot-by-shot plan.
    Generation is pure LLM structured output (see storyboard_service.py) — no image/video
    model inference, so unlike MyBuddy Video this runs inline in the API process, same
    reasoning as Vector's generate_scene."""

    __tablename__ = "storyboards"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    script: Mapped[str] = mapped_column(Text, nullable=False)
    # Consistency inputs (spec §8-9): guidance built from these is prepended to the
    # generation prompt — see storyboard_service.generate_storyboard's `guidance` param and
    # character_service.character_guidance/world_guidance. Stored so a regenerate/edit later
    # can reuse the same consistency inputs without the caller re-specifying them.
    character_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    world_bible_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("world_bibles.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    shots: Mapped[list["StoryboardShot"]] = relationship(
        back_populates="storyboard", cascade="all, delete-orphan", order_by="StoryboardShot.shot_index"
    )
