import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    shots: Mapped[list["StoryboardShot"]] = relationship(
        back_populates="storyboard", cascade="all, delete-orphan", order_by="StoryboardShot.shot_index"
    )
