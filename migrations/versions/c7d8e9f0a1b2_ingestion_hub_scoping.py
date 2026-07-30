"""v6_ingestion_hub_scoping

Revision ID: c7d8e9f0a1b2
Revises: c8d3e4f5a6b7
Create Date: 2026-07-29 17:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'c8d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    columns = [c["name"] for c in _inspector().get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Backfill syntraflow_collections.hub_id if nullable or missing values
    conn.execute(
        sa.text(
            """
            UPDATE syntraflow_collections
            SET hub_id = COALESCE(
                hub_id,
                (SELECT id FROM hubs WHERE hub_type='ingestion' AND slug='default' LIMIT 1),
                '00000000-0000-0000-0000-000000000001'
            )
            WHERE hub_id IS NULL;
            """
        )
    )
    op.alter_column("syntraflow_collections", "hub_id", nullable=False)

    # 2. Backfill physical_name
    conn.execute(
        sa.text(
            """
            UPDATE syntraflow_collections
            SET physical_name = 'default__' || lower(regexp_replace(name, '[^a-z0-9_]+', '_', 'g'))
            WHERE physical_name IS NULL OR physical_name = '';
            """
        )
    )
    op.alter_column("syntraflow_collections", "physical_name", nullable=False)

    # 3. Handle index and constraints on syntraflow_collections
    # Drop old global unique index on name if exists
    existing_indexes = [i["name"] for i in _inspector().get_indexes("syntraflow_collections")]
    if "ix_syntraflow_collections_name" in existing_indexes:
        op.drop_index("ix_syntraflow_collections_name", table_name="syntraflow_collections")

    # Add UniqueConstraint on (hub_id, name)
    existing_unique = [u["name"] for u in _inspector().get_unique_constraints("syntraflow_collections")]
    if "uq_collection_hub_name" not in existing_unique:
        op.create_unique_constraint("uq_collection_hub_name", "syntraflow_collections", ["hub_id", "name"])

    if "uq_syntraflow_collections_physical_name" not in existing_unique:
        try:
            op.create_unique_constraint("uq_syntraflow_collections_physical_name", "syntraflow_collections", ["physical_name"])
        except Exception:
            pass

    # 4. Drop tenant_id if present
    if _has_column("syntraflow_collections", "tenant_id"):
        op.drop_column("syntraflow_collections", "tenant_id")

    # 5. Backfill hub_id & collection_id on documents, chunks, video_segments, jobs
    tables = ["syntraflow_documents", "syntraflow_chunks", "syntraflow_video_segments", "syntraflow_jobs"]
    for t in tables:
        if _has_table(t):
            conn.execute(
                sa.text(
                    f"""
                    UPDATE {t}
                    SET hub_id = COALESCE(
                        hub_id,
                        (SELECT id FROM hubs WHERE hub_type='ingestion' AND slug='default' LIMIT 1),
                        '00000000-0000-0000-0000-000000000001'
                    )
                    WHERE hub_id IS NULL;
                    """
                )
            )
            op.alter_column(t, "hub_id", nullable=False)

    if _has_table("syntraflow_documents") and _has_column("syntraflow_documents", "collection_id"):
        conn.execute(
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
        op.alter_column("syntraflow_documents", "collection_id", nullable=False)


def downgrade() -> None:
    if not _has_column("syntraflow_collections", "tenant_id"):
        op.add_column("syntraflow_collections", sa.Column("tenant_id", sa.String(64), nullable=True, server_default="default"))

    existing_unique = [u["name"] for u in _inspector().get_unique_constraints("syntraflow_collections")]
    if "uq_collection_hub_name" in existing_unique:
        op.drop_constraint("uq_collection_hub_name", "syntraflow_collections", type_="unique")
