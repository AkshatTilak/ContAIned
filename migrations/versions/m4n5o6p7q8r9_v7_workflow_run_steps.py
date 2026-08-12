"""v7_workflow_run_steps

Revision ID: m4n5o6p7q8r9
Revises: l3g4h5i6j7k8
Create Date: 2026-08-11 09:40:00.000000

Adds the workflow_run_steps table for per-node execution telemetry in workflow runs.
Each row records input/output state, latency, status, and sequence for one node
executed within a WorkflowRun.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "m4n5o6p7q8r9"
down_revision: Union[str, Sequence[str], None] = "l3g4h5i6j7k8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add workflow_run_steps table with FKs and indexes."""
    op.create_table(
        "workflow_run_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "hub_id",
            sa.String(36),
            sa.ForeignKey("hubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            sa.String(36),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_id", sa.String(200), nullable=False),
        sa.Column("node_type", sa.String(80), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("input_state", sa.JSON, nullable=True),
        sa.Column("output_state", sa.JSON, nullable=True),
        sa.Column("error_json", sa.JSON, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("latency_ms", sa.Float, nullable=True, server_default="0.0"),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("finished_at", sa.DateTime, nullable=True),
    )
    op.create_index(
        "ix_workflow_run_steps_run_seq",
        "workflow_run_steps",
        ["run_id", "sequence"],
    )
    op.create_index(
        "ix_workflow_run_steps_run_id",
        "workflow_run_steps",
        ["run_id"],
    )
    op.create_index(
        "ix_workflow_run_steps_workflow_id",
        "workflow_run_steps",
        ["workflow_id"],
    )
    op.create_index(
        "ix_workflow_run_steps_hub_id",
        "workflow_run_steps",
        ["hub_id"],
    )


def downgrade() -> None:
    """Drop workflow_run_steps table and its indexes."""
    op.drop_index("ix_workflow_run_steps_hub_id", table_name="workflow_run_steps")
    op.drop_index("ix_workflow_run_steps_workflow_id", table_name="workflow_run_steps")
    op.drop_index("ix_workflow_run_steps_run_id", table_name="workflow_run_steps")
    op.drop_index("ix_workflow_run_steps_run_seq", table_name="workflow_run_steps")
    op.drop_table("workflow_run_steps")
