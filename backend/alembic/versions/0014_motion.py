"""motion projects + clips (MyBuddy Motion)

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "motion_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("canvas_width", sa.Integer(), nullable=False),
        sa.Column("canvas_height", sa.Integer(), nullable=False),
        sa.Column("total_duration_ms", sa.Integer(), nullable=False),
        sa.Column("loop", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_motion_projects_user_id", "motion_projects", ["user_id"])

    op.create_table(
        "motion_clips",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "motion_project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("motion_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "animation_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("animation_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("start_offset_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("x_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("y_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("z_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_motion_clips_motion_project_id", "motion_clips", ["motion_project_id"])
    op.create_index("ix_motion_clips_animation_document_id", "motion_clips", ["animation_document_id"])


def downgrade() -> None:
    op.drop_index("ix_motion_clips_animation_document_id", table_name="motion_clips")
    op.drop_index("ix_motion_clips_motion_project_id", table_name="motion_clips")
    op.drop_table("motion_clips")
    op.drop_index("ix_motion_projects_user_id", table_name="motion_projects")
    op.drop_table("motion_projects")
