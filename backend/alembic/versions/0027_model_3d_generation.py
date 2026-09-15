"""MyBuddy CG: text/image -> 3D mesh generation

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "models_3d",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_models_3d_user_id", "models_3d", ["user_id"])

    op.create_table(
        "model_3d_generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column(
            "source_image_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("images.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("steps", sa.Integer(), nullable=False),
        sa.Column("guidance_scale", sa.Float(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column(
            "model_3d_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("models_3d.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_model_3d_generation_jobs_user_id", "model_3d_generation_jobs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_model_3d_generation_jobs_user_id", table_name="model_3d_generation_jobs")
    op.drop_table("model_3d_generation_jobs")
    op.drop_index("ix_models_3d_user_id", table_name="models_3d")
    op.drop_table("models_3d")
