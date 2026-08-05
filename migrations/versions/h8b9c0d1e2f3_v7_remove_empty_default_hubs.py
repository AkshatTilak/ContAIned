"""Remove resource-empty V6 default hubs from clean installations.

Revision ID: h8b9c0d1e2f3
Revises: g7a8b9c0d1e2
Create Date: 2026-08-04 17:00:00.000000

The V6 cutover had to create four deterministic hubs while migrating existing
resources. V7 no longer creates default workspaces. This migration removes the
legacy hubs only when none of them owns or targets application data, preserving
upgraded installations that still rely on their migrated default hubs.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "h8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "g7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_HUB_IDS = (
    "00000000-0000-0000-0000-0000000000a1",
    "00000000-0000-0000-0000-0000000000a2",
    "00000000-0000-0000-0000-0000000000a3",
    "00000000-0000-0000-0000-0000000000a4",
)

# Memberships, links, and audit rows are metadata created around the defaults;
# every other hub reference represents application data that must be preserved.
RESOURCE_REFERENCES = (
    ("api_keys", "hub_id"),
    ("agent_definitions", "hub_id"),
    ("syntraflow_documents", "hub_id"),
    ("syntraflow_jobs", "hub_id"),
    ("syntraflow_chunks", "hub_id"),
    ("syntraflow_video_segments", "hub_id"),
    ("eval_test_suites", "hub_id"),
    ("eval_test_suites", "target_hub_id"),
    ("eval_run_history", "hub_id"),
    ("eval_run_history", "target_hub_id"),
    ("workflows", "hub_id"),
    ("agent_invocation_log", "hub_id"),
    ("playground_sessions", "hub_id"),
    ("mcp_servers", "hub_id"),
    ("syntraflow_collections", "hub_id"),
    ("eval_flow_traces", "hub_id"),
    ("datastore_bindings", "hub_id"),
    ("workflow_runs", "hub_id"),
)


def _id_clause(sql: str) -> sa.TextClause:
    return sa.text(sql).bindparams(sa.bindparam("hub_ids", expanding=True))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    for table_name, column_name in RESOURCE_REFERENCES:
        if table_name not in table_names:
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if column_name not in columns:
            continue
        count = bind.execute(
            _id_clause(
                f'SELECT COUNT(*) FROM "{table_name}" '
                f'WHERE "{column_name}" IN :hub_ids'
            ),
            {"hub_ids": DEFAULT_HUB_IDS},
        ).scalar_one()
        if count:
            return

    if "hub_links" in table_names:
        bind.execute(
            _id_clause(
                "DELETE FROM hub_links WHERE source_hub_id IN :hub_ids "
                "OR target_hub_id IN :hub_ids"
            ),
            {"hub_ids": DEFAULT_HUB_IDS},
        )
    if "hub_members" in table_names:
        bind.execute(
            _id_clause("DELETE FROM hub_members WHERE hub_id IN :hub_ids"),
            {"hub_ids": DEFAULT_HUB_IDS},
        )
    if "hubs" in table_names:
        bind.execute(
            _id_clause("DELETE FROM hubs WHERE id IN :hub_ids"),
            {"hub_ids": DEFAULT_HUB_IDS},
        )


def downgrade() -> None:
    # Deleted workspace metadata cannot be reconstructed safely. Older code can
    # still create hubs through the normal API after a downgrade.
    pass
