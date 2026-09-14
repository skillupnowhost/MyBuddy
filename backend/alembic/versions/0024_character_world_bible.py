"""CharacterIdentitySystem + WorldBible (video/CG/VFX spec sub-phase 3)

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "characters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("appearance", sa.Text(), nullable=True),
        sa.Column("personality", sa.Text(), nullable=True),
        sa.Column("voice_description", sa.Text(), nullable=True),
        sa.Column(
            "reference_image_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("images.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_characters_user_id", "characters", ["user_id"])

    op.create_table(
        "world_bibles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("setting_description", sa.Text(), nullable=True),
        sa.Column("atmosphere", sa.Text(), nullable=True),
        sa.Column("visual_style", sa.Text(), nullable=True),
        sa.Column("color_palette", sa.Text(), nullable=True),
        sa.Column("rules", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_world_bibles_user_id", "world_bibles", ["user_id"])

    op.add_column("storyboards", sa.Column("character_ids", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column(
        "storyboards",
        sa.Column(
            "world_bible_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("world_bibles.id", ondelete="SET NULL"), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("storyboards", "world_bible_id")
    op.drop_column("storyboards", "character_ids")
    op.drop_index("ix_world_bibles_user_id", table_name="world_bibles")
    op.drop_table("world_bibles")
    op.drop_index("ix_characters_user_id", table_name="characters")
    op.drop_table("characters")
