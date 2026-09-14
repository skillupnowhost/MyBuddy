"""vector documents + objects (MyBuddy Vector)

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vector_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("canvas_width", sa.Integer(), nullable=False),
        sa.Column("canvas_height", sa.Integer(), nullable=False),
        sa.Column("background_color", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_vector_documents_user_id", "vector_documents", ["user_id"])

    op.create_table(
        "vector_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vector_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("object_type", sa.String(length=20), nullable=False),
        sa.Column("z_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("layer_name", sa.String(length=100), nullable=False, server_default="default"),
        sa.Column("props", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_vector_objects_document_id", "vector_objects", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_vector_objects_document_id", table_name="vector_objects")
    op.drop_table("vector_objects")
    op.drop_index("ix_vector_documents_user_id", table_name="vector_documents")
    op.drop_table("vector_documents")
