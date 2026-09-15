"""Link StoryboardShot -> VideoGenerationJob (video/CG/VFX spec sub-phase 5)

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "storyboard_shots",
        sa.Column(
            "video_generation_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_generation_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("storyboard_shots", "video_generation_job_id")
