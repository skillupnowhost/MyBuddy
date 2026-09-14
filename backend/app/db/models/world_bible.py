import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class WorldBible(Base):
    """WorldBible (video/CG/VFX spec §9), same minimal-footprint/prompt-injection-only
    treatment as Character/BrandKit — see character.py's docstring for why this project
    doesn't attempt a real cross-shot visual-consistency ML system. Consolidates the spec's
    longer field list (locations/architecture/weather/time/lighting/materials/objects/
    vehicles/rules/palette/style) into a handful of free-text fields rather than a field per
    concept — a user or an LLM can express "1920s New York, perpetual rain, neon-lit noir"
    just as well in one `atmosphere` field as in five separate ones."""

    __tablename__ = "world_bibles"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    setting_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    atmosphere: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    color_palette: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
