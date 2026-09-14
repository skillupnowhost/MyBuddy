import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class BrandKit(Base):
    """Cross-asset consistency metadata for MyBuddy Creative Director — colors are injected
    into Vector generation prompts (see creative_service.brand_guidance). font_family is
    informational only: VectorObject's TEXT props schema has no font_family field today, so
    nothing enforces a chosen font in the rendered SVG (stated honestly, not glossed over)."""

    __tablename__ = "brand_kits"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    accent_color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    font_family: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
