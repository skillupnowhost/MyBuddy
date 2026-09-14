"""training job cancellation + model promotion lifecycle

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("training_jobs", sa.Column("eval_metrics", sa.JSON(), nullable=True))
    op.add_column("training_jobs", sa.Column("pid", sa.Integer(), nullable=True))

    op.add_column(
        "registered_models",
        sa.Column("capability", sa.String(length=50), nullable=False, server_default="TEXT"),
    )
    op.add_column("registered_models", sa.Column("eval_score", sa.Float(), nullable=True))
    op.add_column("registered_models", sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True))

    # Existing rows were inserted with the old default status of 'READY' by train_lora.py;
    # normalize them into the new promotion lifecycle as EXPERIMENTAL (untested, not yet promoted).
    op.execute("UPDATE registered_models SET status = 'EXPERIMENTAL' WHERE status = 'READY'")
    op.alter_column("registered_models", "status", server_default="EXPERIMENTAL")


def downgrade() -> None:
    op.alter_column("registered_models", "status", server_default="READY")
    op.drop_column("registered_models", "promoted_at")
    op.drop_column("registered_models", "eval_score")
    op.drop_column("registered_models", "capability")
    op.drop_column("training_jobs", "pid")
    op.drop_column("training_jobs", "eval_metrics")
