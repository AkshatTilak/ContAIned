"""v7_external_credentials

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-08-11 09:55:00.000000

Adds the external_credentials table for hub-scoped encrypted database
credentials used by the Task 12 connector pool manager.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "n5o6p7q8r9s0"
down_revision: Union[str, Sequence[str], None] = "m4n5o6p7q8r9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add external_credentials table."""
    op.create_table(
        "external_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "hub_id",
            sa.String(36),
            sa.ForeignKey("hubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("db_type", sa.String(30), nullable=False),
        sa.Column("host", sa.String(500), nullable=True),
        sa.Column("port", sa.Integer, nullable=True),
        sa.Column("database_name", sa.String(200), nullable=True),
        sa.Column("username", sa.String(200), nullable=True),
        sa.Column("encrypted_secret_payload", sa.Text, nullable=True),
        sa.Column("is_read_only", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("max_connections", sa.Integer, nullable=False, server_default="10"),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("hub_id", "name", name="uq_external_credentials_hub_name"),
    )
    op.create_index(
        "ix_external_credentials_hub_id",
        "external_credentials",
        ["hub_id"],
    )


def downgrade() -> None:
    """Drop external_credentials table."""
    op.drop_index("ix_external_credentials_hub_id", table_name="external_credentials")
    op.drop_table("external_credentials")
