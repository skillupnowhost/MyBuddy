import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID

# Runs as a plain OS subprocess (see SubprocessSandboxProvider), never inline in the API
# process. Lifecycle: PENDING -> RUNNING -> COMPLETED|FAILED|TIMEOUT|CANCELLED.
CODE_EXECUTION_STATUSES = ("PENDING", "RUNNING", "COMPLETED", "FAILED", "TIMEOUT", "CANCELLED")


class CodeExecutionJob(Base):
    __tablename__ = "code_execution_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    stderr_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
