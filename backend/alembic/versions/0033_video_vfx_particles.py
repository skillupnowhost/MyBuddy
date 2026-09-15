"""AI VFX particle overlays for video (video/CG/VFX spec §17)

Revision ID: 0033
Revises: 0032
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("video_edit_jobs", sa.Column("vfx_type", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("video_edit_jobs", "vfx_type")
