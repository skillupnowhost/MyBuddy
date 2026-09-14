"""model registry provider column (phase 9: local-only frontier router)

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "registered_models", sa.Column("provider", sa.String(length=50), nullable=False, server_default="LOCAL")
    )


def downgrade() -> None:
    op.drop_column("registered_models", "provider")
