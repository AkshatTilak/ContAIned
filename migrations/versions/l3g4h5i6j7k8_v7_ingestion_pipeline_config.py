"""v7_ingestion_pipeline_config

Revision ID: l3g4h5i6j7k8
Revises: k2f3a4b5c6d7
Create Date: 2026-08-07 14:15:00.000000

Adds pipeline_config_json column to syntraflow_jobs and syntraflow_collections tables for document-type-aware ingestion pipeline configuration.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "l3g4h5i6j7k8"
down_revision: Union[str, Sequence[str], None] = "k2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add pipeline_config_json columns to syntraflow_jobs and syntraflow_collections."""
    op.add_column("syntraflow_jobs", sa.Column("pipeline_config_json", sa.JSON(), nullable=True))
    op.add_column("syntraflow_collections", sa.Column("pipeline_config_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove pipeline_config_json columns."""
    op.drop_column("syntraflow_collections", "pipeline_config_json")
    op.drop_column("syntraflow_jobs", "pipeline_config_json")
