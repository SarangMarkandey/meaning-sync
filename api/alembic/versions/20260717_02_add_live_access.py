"""add role-bound Live access and invitations

Revision ID: 20260717_02
Revises: 20260717_01
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260717_02"
down_revision: str | None = "20260717_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_access_credentials",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("session_id", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"], ["live_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_live_access_credentials_session_id",
        "live_access_credentials",
        ["session_id"],
    )
    op.create_index(
        "ix_live_access_credentials_token_hash",
        "live_access_credentials",
        ["token_hash"],
        unique=True,
    )
    op.create_table(
        "live_session_invitations",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("session_id", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("invitation_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exchanged_access_id", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"], ["live_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_live_session_invitations_session_id",
        "live_session_invitations",
        ["session_id"],
    )
    op.create_index(
        "ix_live_session_invitations_invitation_hash",
        "live_session_invitations",
        ["invitation_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_live_session_invitations_invitation_hash",
        table_name="live_session_invitations",
    )
    op.drop_index(
        "ix_live_session_invitations_session_id",
        table_name="live_session_invitations",
    )
    op.drop_table("live_session_invitations")
    op.drop_index(
        "ix_live_access_credentials_token_hash",
        table_name="live_access_credentials",
    )
    op.drop_index(
        "ix_live_access_credentials_session_id",
        table_name="live_access_credentials",
    )
    op.drop_table("live_access_credentials")
