"""model benchmark results (phase 9: model benchmark engine & arena)

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_benchmark_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "model_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registered_models.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prompt_id", sa.String(length=100), nullable=False),
        sa.Column("capability", sa.String(length=50), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("response_preview", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_model_benchmark_results_model_id", "model_benchmark_results", ["model_id"])


def downgrade() -> None:
    op.drop_table("model_benchmark_results")
