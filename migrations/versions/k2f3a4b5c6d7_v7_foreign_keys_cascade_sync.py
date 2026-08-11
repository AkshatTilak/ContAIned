"""v7_foreign_keys_cascade_sync

Revision ID: k2f3a4b5c6d7
Revises: j1e2f3a4b5c6
Create Date: 2026-08-07 12:00:00.000000

Syncs foreign key ON DELETE CASCADE rules for document child tables (syntraflow_jobs, syntraflow_chunks, syntraflow_video_segments).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "k2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "9505282eda4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ON DELETE CASCADE to document foreign keys across SyntraFlow tables."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # syntraflow_jobs -> syntraflow_documents
    try:
        op.drop_constraint("syntraflow_jobs_document_id_fkey", "syntraflow_jobs", type_="foreignkey")
    except Exception:
        pass
    try:
        op.create_foreign_key(
            "syntraflow_jobs_document_id_fkey",
            "syntraflow_jobs",
            "syntraflow_documents",
            ["document_id"],
            ["id"],
            ondelete="CASCADE",
        )
    except Exception:
        pass

    # syntraflow_chunks -> syntraflow_documents
    try:
        op.drop_constraint("syntraflow_chunks_document_id_fkey", "syntraflow_chunks", type_="foreignkey")
    except Exception:
        pass
    try:
        op.create_foreign_key(
            "syntraflow_chunks_document_id_fkey",
            "syntraflow_chunks",
            "syntraflow_documents",
            ["document_id"],
            ["id"],
            ondelete="CASCADE",
        )
    except Exception:
        pass

    # syntraflow_video_segments -> syntraflow_documents
    try:
        op.drop_constraint("syntraflow_video_segments_document_id_fkey", "syntraflow_video_segments", type_="foreignkey")
    except Exception:
        pass
    try:
        op.create_foreign_key(
            "syntraflow_video_segments_document_id_fkey",
            "syntraflow_video_segments",
            "syntraflow_documents",
            ["document_id"],
            ["id"],
            ondelete="CASCADE",
        )
    except Exception:
        pass


def downgrade() -> None:
    pass
