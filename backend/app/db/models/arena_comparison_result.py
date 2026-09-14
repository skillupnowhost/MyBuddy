import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class ArenaComparisonResult(Base):
    """One model's answer to one ad-hoc admin-supplied prompt, from one Model Arena run
    (see arena_service.py). `comparison_id` groups every row produced by a single
    POST /admin/arena/compare call — unlike ModelBenchmarkResult's fixed prompt suite, an
    arena prompt is arbitrary, so there's no prompt_id to group by instead. `score` is null
    when the run had no reference_answer to compare against (side-by-side human judgment)."""

    __tablename__ = "arena_comparison_results"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    comparison_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    model_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("registered_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
