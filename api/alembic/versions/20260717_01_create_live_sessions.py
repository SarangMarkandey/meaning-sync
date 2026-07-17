"""create durable Live sessions

Revision ID: 20260717_01
Revises:
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260717_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_sessions",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("state_schema_version", sa.Integer(), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_live_sessions_expires_at", "live_sessions", ["expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_live_sessions_expires_at", table_name="live_sessions")
    op.drop_table("live_sessions")
