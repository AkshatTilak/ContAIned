"""v7_collections_schema_sync

Revision ID: j1e2f3a4b5c6
Revises: i9c0d1e2f3a4
Create Date: 2026-08-05 12:10:00.000000

Adds columns and tables that were defined in SQLAlchemy models but missing from Alembic migrations:
1. syntraflow_collections: retrieval_config_json, datastore_binding_id
2. syntraflow_documents: collection_id
3. syntraflow_jobs: collection_id
4. api_key_usage table
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "j1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "i9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table: str) -> bool:
    return _inspector().has_table(table)


def _has_column(table: str, column: str) -> bool:
    insp = _inspector()
    if not insp.has_table(table):
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    """Sync all missing columns and tables to match SQLAlchemy models."""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 1. syntraflow_collections missing columns
    if not _has_column("syntraflow_collections", "retrieval_config_json"):
        with op.batch_alter_table("syntraflow_collections") as batch_op:
            batch_op.add_column(
                sa.Column("retrieval_config_json", sa.JSON(), nullable=False, server_default="{}"),
            )
    if not _has_column("syntraflow_collections", "datastore_binding_id"):
        with op.batch_alter_table("syntraflow_collections") as batch_op:
            if is_sqlite:
                batch_op.add_column(
                    sa.Column("datastore_binding_id", sa.String(length=36), nullable=True)
                )
            else:
                batch_op.add_column(
                    sa.Column(
                        "datastore_binding_id",
                        sa.String(length=36),
                        sa.ForeignKey("datastore_bindings.id", ondelete="SET NULL"),
                        nullable=True,
                    )
                )

    # 2. syntraflow_documents.collection_id
    if not _has_column("syntraflow_documents", "collection_id"):
        with op.batch_alter_table("syntraflow_documents") as batch_op:
            if is_sqlite:
                batch_op.add_column(
                    sa.Column("collection_id", sa.String(length=36), nullable=True)
                )
            else:
                batch_op.add_column(
                    sa.Column(
                        "collection_id",
                        sa.String(length=36),
                        sa.ForeignKey("syntraflow_collections.id", ondelete="CASCADE"),
                        nullable=True,
                    )
                )
        # Backfill collection_id if any existing documents
        bind.execute(
            sa.text(
                """
                UPDATE syntraflow_documents
                SET collection_id = COALESCE(
                    collection_id,
                    (SELECT id FROM syntraflow_collections WHERE hub_id = syntraflow_documents.hub_id LIMIT 1),
                    (SELECT id FROM syntraflow_collections LIMIT 1)
                )
                WHERE collection_id IS NULL;
                """
            )
        )

    # 3. syntraflow_jobs.collection_id
    if not _has_column("syntraflow_jobs", "collection_id"):
        with op.batch_alter_table("syntraflow_jobs") as batch_op:
            if is_sqlite:
                batch_op.add_column(
                    sa.Column("collection_id", sa.String(length=36), nullable=True)
                )
            else:
                batch_op.add_column(
                    sa.Column(
                        "collection_id",
                        sa.String(length=36),
                        sa.ForeignKey("syntraflow_collections.id", ondelete="CASCADE"),
                        nullable=True,
                    )
                )
        # Backfill collection_id if any existing jobs
        bind.execute(
            sa.text(
                """
                UPDATE syntraflow_jobs
                SET collection_id = COALESCE(
                    collection_id,
                    (SELECT id FROM syntraflow_collections WHERE hub_id = syntraflow_jobs.hub_id LIMIT 1),
                    (SELECT id FROM syntraflow_collections LIMIT 1)
                )
                WHERE collection_id IS NULL;
                """
            )
        )

    # 4. api_key_usage table
    if not _has_table("api_key_usage"):
        op.create_table(
            "api_key_usage",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "api_key_id",
                sa.Integer(),
                sa.ForeignKey("api_keys.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("endpoint", sa.String(length=200), nullable=False),
            sa.Column("model_used", sa.String(length=200), nullable=True),
            sa.Column("input_tokens", sa.Integer(), server_default="0"),
            sa.Column("output_tokens", sa.Integer(), server_default="0"),
            sa.Column("latency_ms", sa.Float(), nullable=True),
            sa.Column("status_code", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    if _has_table("api_key_usage"):
        op.drop_table("api_key_usage")

    if _has_column("syntraflow_jobs", "collection_id"):
        with op.batch_alter_table("syntraflow_jobs") as batch_op:
            batch_op.drop_column("collection_id")

    if _has_column("syntraflow_documents", "collection_id"):
        with op.batch_alter_table("syntraflow_documents") as batch_op:
            batch_op.drop_column("collection_id")

    if _has_column("syntraflow_collections", "datastore_binding_id"):
        with op.batch_alter_table("syntraflow_collections") as batch_op:
            batch_op.drop_column("datastore_binding_id")

    if _has_column("syntraflow_collections", "retrieval_config_json"):
        with op.batch_alter_table("syntraflow_collections") as batch_op:
            batch_op.drop_column("retrieval_config_json")
