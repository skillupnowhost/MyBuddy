"""AI Object Removal for video (video/CG/VFX spec §21)

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "video_edit_jobs",
        sa.Column(
            "mask_image_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("images.id", ondelete="SET NULL"), nullable=True
        ),
    )
    op.add_column("video_edit_jobs", sa.Column("prompt", sa.Text(), nullable=True))
    op.add_column("video_edit_jobs", sa.Column("negative_prompt", sa.Text(), nullable=True))
    op.add_column("video_edit_jobs", sa.Column("steps", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("video_edit_jobs", "steps")
    op.drop_column("video_edit_jobs", "negative_prompt")
    op.drop_column("video_edit_jobs", "prompt")
    op.drop_column("video_edit_jobs", "mask_image_id")
