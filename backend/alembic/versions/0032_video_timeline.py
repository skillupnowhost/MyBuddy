"""MyBuddy Video Editor: non-destructive timeline + export (video/CG/VFX spec §30-31)

Revision ID: 0032
Revises: 0031
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "video_timelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_video_timelines_user_id", "video_timelines", ["user_id"])

    op.create_table(
        "video_timeline_clips",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "timeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("video_timelines.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("clip_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trim_start_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("trim_end_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_video_timeline_clips_timeline_id", "video_timeline_clips", ["timeline_id"])
    op.create_index("ix_video_timeline_clips_video_id", "video_timeline_clips", ["video_id"])

    op.create_table(
        "video_timeline_export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "timeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("video_timelines.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column(
            "result_video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_video_timeline_export_jobs_user_id", "video_timeline_export_jobs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_video_timeline_export_jobs_user_id", table_name="video_timeline_export_jobs")
    op.drop_table("video_timeline_export_jobs")
    op.drop_index("ix_video_timeline_clips_video_id", table_name="video_timeline_clips")
    op.drop_index("ix_video_timeline_clips_timeline_id", table_name="video_timeline_clips")
    op.drop_table("video_timeline_clips")
    op.drop_index("ix_video_timelines_user_id", table_name="video_timelines")
    op.drop_table("video_timelines")
