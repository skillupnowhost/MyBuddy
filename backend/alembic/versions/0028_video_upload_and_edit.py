"""Video upload + green screen / background removal editing (video/CG/VFX spec §18-20)

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # width/height/duration_seconds are only known for generated videos (the job controlled
    # them); an uploaded video's are left null — see db/models/video.py's docstring.
    op.alter_column("videos", "width", existing_type=sa.Integer(), nullable=True)
    op.alter_column("videos", "height", existing_type=sa.Integer(), nullable=True)
    op.alter_column("videos", "duration_seconds", existing_type=sa.Float(), nullable=True)

    op.create_table(
        "video_edit_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column(
            "source_video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("background_color", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column(
            "result_video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_video_edit_jobs_user_id", "video_edit_jobs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_video_edit_jobs_user_id", table_name="video_edit_jobs")
    op.drop_table("video_edit_jobs")
    op.alter_column("videos", "duration_seconds", existing_type=sa.Float(), nullable=False)
    op.alter_column("videos", "height", existing_type=sa.Integer(), nullable=False)
    op.alter_column("videos", "width", existing_type=sa.Integer(), nullable=False)
