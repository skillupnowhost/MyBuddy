"""animation documents + keyframes (MyBuddy Animator)

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "animation_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vector_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vector_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("frame_rate", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("loop", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_animation_documents_user_id", "animation_documents", ["user_id"])
    op.create_index("ix_animation_documents_vector_document_id", "animation_documents", ["vector_document_id"])

    op.create_table(
        "animation_keyframes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "animation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("animation_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vector_objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("time_ms", sa.Integer(), nullable=False),
        sa.Column("prop", sa.String(length=30), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("easing", sa.String(length=20), nullable=False, server_default="LINEAR"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_animation_keyframes_animation_id", "animation_keyframes", ["animation_id"])
    op.create_index("ix_animation_keyframes_object_id", "animation_keyframes", ["object_id"])


def downgrade() -> None:
    op.drop_index("ix_animation_keyframes_object_id", table_name="animation_keyframes")
    op.drop_index("ix_animation_keyframes_animation_id", table_name="animation_keyframes")
    op.drop_table("animation_keyframes")
    op.drop_index("ix_animation_documents_vector_document_id", table_name="animation_documents")
    op.drop_index("ix_animation_documents_user_id", table_name="animation_documents")
    op.drop_table("animation_documents")
