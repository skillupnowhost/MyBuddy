"""StoryboardGenerator (video/CG/VFX spec sub-phase 2)

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "storyboards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("script", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_storyboards_user_id", "storyboards", ["user_id"])

    op.create_table(
        "storyboard_shots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "storyboard_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("storyboards.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("shot_index", sa.Integer(), nullable=False),
        sa.Column("scene_id", sa.String(length=100), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("camera", sa.String(length=255), nullable=False),
        sa.Column("lens", sa.String(length=100), nullable=True),
        sa.Column("composition", sa.String(length=255), nullable=True),
        sa.Column("characters", sa.JSON(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("environment", sa.Text(), nullable=False),
        sa.Column("lighting", sa.String(length=255), nullable=True),
        sa.Column("dialogue", sa.Text(), nullable=True),
        sa.Column("sound", sa.Text(), nullable=True),
        sa.Column("vfx", sa.Text(), nullable=True),
        sa.Column("generation_prompt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_storyboard_shots_storyboard_id", "storyboard_shots", ["storyboard_id"])


def downgrade() -> None:
    op.drop_table("storyboard_shots")
    op.drop_index("ix_storyboards_user_id", table_name="storyboards")
    op.drop_table("storyboards")
