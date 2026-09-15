"""Default tools_enabled to true for new conversations

Users had no way to discover the "Allow tools" toggle, so date/time and
calculator questions silently failed in every new conversation until they
found and checked it themselves. Existing conversations keep whatever value
they already have — this only changes what new rows default to.

Revision ID: 0034
Revises: 0033
Create Date: 2026-09-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("conversations", "tools_enabled", server_default=sa.true())


def downgrade() -> None:
    op.alter_column("conversations", "tools_enabled", server_default=sa.false())
