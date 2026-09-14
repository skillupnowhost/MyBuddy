"""CameraPlanner (video/CG/VFX spec sub-phase 4)

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "camera_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "storyboard_shot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("storyboard_shots.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("motion_type", sa.String(length=20), nullable=False, server_default="STATIC"),
        sa.Column("lens", sa.String(length=100), nullable=True),
        sa.Column("focal_length_mm", sa.Float(), nullable=True),
        sa.Column("aperture", sa.Float(), nullable=True),
        sa.Column("shutter_speed", sa.String(length=50), nullable=True),
        sa.Column("depth_of_field", sa.String(length=100), nullable=True),
        sa.Column("motion_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_camera_plans_user_id", "camera_plans", ["user_id"])
    op.create_index("ix_camera_plans_storyboard_shot_id", "camera_plans", ["storyboard_shot_id"])


def downgrade() -> None:
    op.drop_table("camera_plans")
