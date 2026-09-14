import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class AnimationKeyframe(Base):
    """At `time_ms`, the target object's `prop` should be `value` — the same typed-prop-
    mutation concept as VectorObject SET_PROP, with a time axis. `value` is JSON (float or
    str) since props vary by type, mirroring VectorObject.props; validated via
    vector_service.validate_prop_value before ever being written here, same as VectorObject."""

    __tablename__ = "animation_keyframes"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    animation_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("animation_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("vector_objects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    prop: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[float | str] = mapped_column(JSON, nullable=False)
    easing: Mapped[str] = mapped_column(String(20), nullable=False, default="LINEAR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    animation: Mapped["AnimationDocument"] = relationship(back_populates="keyframes")
