import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class CreativeProject(Base):
    """Groups assets (Vector documents, Animator animations, Motion projects) produced across
    the other Creative Platform phases, optionally with a BrandKit for cross-asset
    consistency. Orchestration = fanning out to each phase's existing generation function
    with brand guidance prepended — no new generation protocol of its own."""

    __tablename__ = "creative_projects"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_kit_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("brand_kits.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    assets: Mapped[list["CreativeAsset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="CreativeAsset.created_at"
    )
