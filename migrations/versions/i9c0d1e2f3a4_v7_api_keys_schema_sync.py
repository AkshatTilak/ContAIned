"""v7_api_keys_schema_sync

Revision ID: i9c0d1e2f3a4
Revises: h8b9c0d1e2f3
Create Date: 2026-08-04 17:30:00.000000

Adds columns to api_keys that were defined in the SQLAlchemy model but never
migrated: prefix, rate_limit, user_id, usage_count, last_used_at.
The hub_id column was already added by a6b1c2d3e4f5 (V6 stage1).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "i9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "h8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_column(table: str, column: str) -> bool:
    insp = _inspector()
    if not insp.has_table(table):
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    """Add missing columns to api_keys to match the SQLAlchemy model."""
    if not _has_column("api_keys", "prefix"):
        op.add_column(
            "api_keys",
            sa.Column("prefix", sa.String(length=20), nullable=True),
        )
    if not _has_column("api_keys", "rate_limit"):
        op.add_column(
            "api_keys",
            sa.Column("rate_limit", sa.Integer(), nullable=True, server_default="60"),
        )
    if not _has_column("api_keys", "user_id"):
        op.add_column(
            "api_keys",
            sa.Column(
                "user_id",
                sa.String(length=36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"], unique=False)
    if not _has_column("api_keys", "usage_count"):
        op.add_column(
            "api_keys",
            sa.Column("usage_count", sa.Integer(), nullable=True, server_default="0"),
        )
    if not _has_column("api_keys", "last_used_at"):
        op.add_column(
            "api_keys",
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("api_keys", "last_used_at"):
        op.drop_column("api_keys", "last_used_at")
    if _has_column("api_keys", "usage_count"):
        op.drop_column("api_keys", "usage_count")
    if _has_column("api_keys", "user_id"):
        try:
            op.drop_index("ix_api_keys_user_id", table_name="api_keys")
        except Exception:
            pass
        op.drop_column("api_keys", "user_id")
    if _has_column("api_keys", "rate_limit"):
        op.drop_column("api_keys", "rate_limit")
    if _has_column("api_keys", "prefix"):
        op.drop_column("api_keys", "prefix")
