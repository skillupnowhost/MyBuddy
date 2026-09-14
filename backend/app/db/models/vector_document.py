import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID

# GENERAL matches Vector's original behavior exactly (unchanged prompt/defaults). The other
# three bias generation toward illustration/logo/icon conventions — see
# vector_service.py's _PURPOSE_GUIDANCE and config.py's vector_purpose_defaults.
VECTOR_DOCUMENT_PURPOSES = ("GENERAL", "ILLUSTRATION", "LOGO", "ICON")


class VectorDocument(Base):
    __tablename__ = "vector_documents"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False, default="GENERAL")
    canvas_width: Mapped[int] = mapped_column(Integer, nullable=False)
    canvas_height: Mapped[int] = mapped_column(Integer, nullable=False)
    background_color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    objects: Mapped[list["VectorObject"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="VectorObject.z_index"
    )
