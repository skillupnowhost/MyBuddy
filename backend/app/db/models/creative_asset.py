import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID

# A polymorphic membership row: asset_id points at one of three different tables depending on
# asset_type, so it's deliberately NOT a DB-level foreign key — ownership/existence is checked
# at the application layer (api/v1/endpoints/creative.py), the standard tradeoff of a
# polymorphic-association design.
CREATIVE_ASSET_TYPES = ("VECTOR", "ANIMATION", "MOTION", "STORYBOARD", "VIDEO", "MODEL_3D")


class CreativeAsset(Base):
    __tablename__ = "creative_assets"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    creative_project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("creative_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["CreativeProject"] = relationship(back_populates="assets")
