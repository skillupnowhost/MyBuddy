import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID

# Promotion lifecycle (see spec §13): a fine-tune lands as EXPERIMENTAL, must be evaluated
# before it can go to CANARY, and only an explicit admin action promotes CANARY -> PRODUCTION.
# Only one RegisteredModel per base_model may hold PRODUCTION at a time; promoting a new one
# demotes the previous holder to ARCHIVED (never deleted, so rollback can restore it).
MODEL_REGISTRY_STATUSES = ("EXPERIMENTAL", "CANARY", "STAGING", "PRODUCTION", "ARCHIVED", "REJECTED")

# Only LOCAL (Ollama) is implemented — no cloud provider has an API key configured on this
# deployment by design (see FrontierModelRouter). The column exists so a future provider is
# a new value + a new Provider class here, not a schema change.
MODEL_PROVIDERS = ("LOCAL",)


class RegisteredModel(Base):
    """A deployable model artifact — either the base model or a completed fine-tune.
    training_job_id is null for base models registered manually."""

    __tablename__ = "registered_models"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")
    base_model: Mapped[str] = mapped_column(String(255), nullable=False)
    capability: Mapped[str] = mapped_column(String(50), nullable=False, default="TEXT")
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="LOCAL")
    training_job_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("training_jobs.id", ondelete="SET NULL"), nullable=True
    )
    quantization: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="EXPERIMENTAL")
    eval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
