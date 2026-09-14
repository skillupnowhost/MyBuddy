"""vector document purpose (MyBuddy Illustrator presets)

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vector_documents", sa.Column("purpose", sa.String(length=20), nullable=False, server_default="GENERAL")
    )


def downgrade() -> None:
    op.drop_column("vector_documents", "purpose")
