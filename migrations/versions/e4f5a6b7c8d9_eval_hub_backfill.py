"""v6_eval_hub_backfill

Revision ID: e4f5a6b7c8d9
Revises: e3f4a5b6c7d8
Create Date: 2026-07-30 12:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, Sequence[str], None] = 'e3f4a5b6c7d8'
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

    # 1. Resolve default seed hub IDs
    eval_hub_id = None
    agent_hub_id = None

    if _has_table("hubs"):
        res = conn.execute(sa.text("SELECT id, hub_type FROM hubs WHERE slug IN ('eval-default', 'default', 'eval') OR hub_type IN ('eval', 'agent')"))
        rows = res.fetchall()
        for r_id, r_type in rows:
            if r_type == "eval" and not eval_hub_id:
                eval_hub_id = r_id
            elif r_type == "agent" and not agent_hub_id:
                agent_hub_id = r_id

    eval_hub_id = eval_hub_id or "eval-default-id"
    agent_hub_id = agent_hub_id or "agent-default-id"

    # 2. Backfill eval_test_suites
    if _has_table("eval_test_suites"):
        if _has_column("eval_test_suites", "agent_id"):
            conn.execute(sa.text(
                "UPDATE eval_test_suites SET "
                "hub_id = COALESCE(hub_id, :eval_hub), "
                "target_type = COALESCE(target_type, 'agent'), "
                "target_hub_id = COALESCE(target_hub_id, :agent_hub), "
                "target_id = COALESCE(target_id, agent_id) "
                "WHERE hub_id IS NULL OR target_id IS NULL"
            ), {"eval_hub": eval_hub_id, "agent_hub": agent_hub_id})

        # Drop agent_id column if present
        if _has_column("eval_test_suites", "agent_id"):
            try:
                op.drop_column("eval_test_suites", "agent_id")
            except Exception:
                pass

    # 3. Backfill eval_run_history
    if _has_table("eval_run_history"):
        if _has_column("eval_run_history", "agent_id"):
            conn.execute(sa.text(
                "UPDATE eval_run_history SET "
                "hub_id = COALESCE(hub_id, :eval_hub), "
                "target_type = COALESCE(target_type, 'agent'), "
                "target_hub_id = COALESCE(target_hub_id, :agent_hub), "
                "target_id = COALESCE(target_id, agent_id) "
                "WHERE hub_id IS NULL OR target_id IS NULL"
            ), {"eval_hub": eval_hub_id, "agent_hub": agent_hub_id})

        if _has_column("eval_run_history", "agent_id"):
            try:
                op.drop_column("eval_run_history", "agent_id")
            except Exception:
                pass

    # 4. Backfill eval_flow_traces
    if _has_table("eval_flow_traces") and _has_column("eval_flow_traces", "hub_id"):
        conn.execute(sa.text(
            "UPDATE eval_flow_traces SET hub_id = :eval_hub WHERE hub_id IS NULL"
        ), {"eval_hub": eval_hub_id})


def downgrade() -> None:
    # Downgrade logic: re-add agent_id if absent and populate from target_id
    if _has_table("eval_test_suites"):
        if not _has_column("eval_test_suites", "agent_id"):
            op.add_column("eval_test_suites", sa.Column("agent_id", sa.String(36), sa.ForeignKey("agent_definitions.id", ondelete="CASCADE"), nullable=True))
            conn = op.get_bind()
            conn.execute(sa.text("UPDATE eval_test_suites SET agent_id = target_id WHERE target_type = 'agent'"))

    if _has_table("eval_run_history"):
        if not _has_column("eval_run_history", "agent_id"):
            op.add_column("eval_run_history", sa.Column("agent_id", sa.String(36), sa.ForeignKey("agent_definitions.id", ondelete="CASCADE"), nullable=True))
            conn = op.get_bind()
            conn.execute(sa.text("UPDATE eval_run_history SET agent_id = target_id WHERE target_type = 'agent'"))
