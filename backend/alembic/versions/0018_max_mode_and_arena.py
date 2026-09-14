"""MAX mode + model arena (phase 9 sub-phase 3)

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("max_mode_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "max_mode_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "model_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registered_models.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("base_model", sa.String(length=255), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("is_judge", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_max_mode_candidates_message_id", "max_mode_candidates", ["message_id"])

    op.create_table(
        "arena_comparison_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("comparison_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "model_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registered_models.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("capability", sa.String(length=50), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_arena_comparison_results_comparison_id", "arena_comparison_results", ["comparison_id"])
    op.create_index("ix_arena_comparison_results_model_id", "arena_comparison_results", ["model_id"])


def downgrade() -> None:
    op.drop_table("arena_comparison_results")
    op.drop_table("max_mode_candidates")
    op.drop_column("conversations", "max_mode_enabled")
