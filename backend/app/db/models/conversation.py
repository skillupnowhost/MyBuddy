import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="New conversation")
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rag_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Defaults on (unlike the other opt-in flags below) so a new conversation can answer
    # basic tool-backed questions (date/time, calculator) without the user discovering and
    # flipping a toggle first — see conversations.py's create endpoint and the 0034 migration.
    tools_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # MAX mode (phase 9 sub-phase 3): fan a turn out to every PRODUCTION/CANARY model for the
    # conversation's capability, then synthesize one judged reply — see
    # chat_service._max_mode_reply. A no-op (falls back to the normal single-model path) when
    # fewer than 2 candidates are registered, same honest scope cut as FAST/BEST/etc. in
    # model_router.py.
    max_mode_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Expert Collaboration Pipeline (phase 9 sub-phase 4): Planner -> Reasoning/Coding/Tool ->
    # Verification -> Synthesizer, see expert_pipeline_service.py. Mutually exclusive with
    # max_mode_enabled — enforced in the conversations endpoint, not here, since that check
    # needs the *resulting* state of a partial PATCH, not just this column in isolation.
    expert_pipeline_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Bounded Agent Orchestration (phase 9 sub-phase 6): lets the model call tools repeatedly
    # (up to agent_service.MAX_AGENT_STEPS) instead of at most once per turn — see
    # agent_service.run_agent_loop. Mutually exclusive with max_mode_enabled and
    # expert_pipeline_enabled — same "resulting state" validation pattern in the
    # conversations endpoint as those two.
    agent_mode_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # When set, chat_service retrieves from this code project instead of the general
    # document RAG store — mutually exclusive with rag_enabled for v1.
    code_project_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("code_projects.id", ondelete="SET NULL"), nullable=True
    )
    # Project Workspaces (phase 9 sub-phase 5): optional grouping, see db/models/workspace.py.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )
