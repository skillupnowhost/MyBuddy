"""Expert Collaboration Pipeline (phase 9 sub-phase 4)

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("expert_pipeline_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "expert_pipeline_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=20), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("raw_output", sa.Text(), nullable=False),
        sa.Column("verified_output", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_expert_pipeline_steps_message_id", "expert_pipeline_steps", ["message_id"])


def downgrade() -> None:
    op.drop_table("expert_pipeline_steps")
    op.drop_column("conversations", "expert_pipeline_enabled")
