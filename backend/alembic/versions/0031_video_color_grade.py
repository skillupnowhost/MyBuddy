"""AI Color Grading for video (video/CG/VFX spec §24/§29)

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("video_edit_jobs", sa.Column("color_preset", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("video_edit_jobs", "color_preset")
