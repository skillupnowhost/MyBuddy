"""code projects/files/chunks + sandbox execution jobs

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("storage_dir", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="UPLOADING"),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_code_projects_user_id", "code_projects", ["user_id"])

    op.create_table(
        "code_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("code_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relative_path", sa.String(length=1000), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("language", sa.String(length=30), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_code_files_project_id", "code_files", ["project_id"])

    op.create_table(
        "code_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("code_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_code_chunks_file_id", "code_chunks", ["file_id"])

    op.create_table(
        "code_execution_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=30), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("stdout_truncated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stderr_truncated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_code_execution_jobs_user_id", "code_execution_jobs", ["user_id"])

    op.add_column(
        "conversations",
        sa.Column(
            "code_project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("code_projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "code_project_id")
    op.drop_index("ix_code_execution_jobs_user_id", table_name="code_execution_jobs")
    op.drop_table("code_execution_jobs")
    op.drop_index("ix_code_chunks_file_id", table_name="code_chunks")
    op.drop_table("code_chunks")
    op.drop_index("ix_code_files_project_id", table_name="code_files")
    op.drop_table("code_files")
    op.drop_index("ix_code_projects_user_id", table_name="code_projects")
    op.drop_table("code_projects")
