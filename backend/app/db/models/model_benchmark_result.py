import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class ModelBenchmarkResult(Base):
    """One prompt's result from one benchmark run against one RegisteredModel — see
    benchmark_service.py for the fixed prompt suite and scoring. Kept even after newer runs
    so the arena view can show history, not just the latest score."""

    __tablename__ = "model_benchmark_results"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("registered_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    capability: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    response_preview: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
