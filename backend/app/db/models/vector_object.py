import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID

VECTOR_OBJECT_TYPES = ("RECT", "CIRCLE", "ELLIPSE", "LINE", "POLYGON", "PATH", "TEXT")


class VectorObject(Base):
    """One shape within a VectorDocument. Type-specific fields (x/y/width/height, cx/cy/r,
    points, path d, text content, ...) live inline in `props` as JSON rather than one column
    per possible field across every object type — validated against a typed Pydantic schema
    (see schemas/vector.py) before ever being written here, so this column is never raw
    untrusted input despite being JSON."""

    __tablename__ = "vector_objects"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("vector_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_type: Mapped[str] = mapped_column(String(20), nullable=False)
    z_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    layer_name: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    props: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    document: Mapped["VectorDocument"] = relationship(back_populates="objects")
