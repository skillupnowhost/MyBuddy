"""brand kits, creative projects + assets (MyBuddy Creative Director)

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brand_kits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("primary_color", sa.String(length=30), nullable=True),
        sa.Column("secondary_color", sa.String(length=30), nullable=True),
        sa.Column("accent_color", sa.String(length=30), nullable=True),
        sa.Column("font_family", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_brand_kits_user_id", "brand_kits", ["user_id"])

    op.create_table(
        "creative_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "brand_kit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brand_kits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_creative_projects_user_id", "creative_projects", ["user_id"])

    op.create_table(
        "creative_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "creative_project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("creative_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asset_type", sa.String(length=20), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_creative_assets_creative_project_id", "creative_assets", ["creative_project_id"])


def downgrade() -> None:
    op.drop_index("ix_creative_assets_creative_project_id", table_name="creative_assets")
    op.drop_table("creative_assets")
    op.drop_index("ix_creative_projects_user_id", table_name="creative_projects")
    op.drop_table("creative_projects")
    op.drop_index("ix_brand_kits_user_id", table_name="brand_kits")
    op.drop_table("brand_kits")
