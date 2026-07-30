"""v6_workflow_hub_models

Revision ID: e1f2a3b4c5d6
Revises: e0f1a2b3c4d5
Create Date: 2026-07-30 11:30:00.000000

"""
import re
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'e0f1a2b3c4d5'
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


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-') or 'workflow'


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create workflow_versions table if missing
    if not _has_table("workflow_versions"):
        op.create_table(
            "workflow_versions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("graph_json", sa.JSON(), nullable=False),
            sa.Column("change_note", sa.String(255), nullable=True),
            sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("validation_json", sa.JSON(), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), default=datetime.utcnow),
            sa.UniqueConstraint("workflow_id", "version_number", name="uq_workflow_versions_number"),
        )

    # 2. Create workflow_runs table if missing
    if not _has_table("workflow_runs"):
        op.create_table(
            "workflow_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("hub_id", sa.String(36), sa.ForeignKey("hubs.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("version_id", sa.String(36), sa.ForeignKey("workflow_versions.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("trigger", sa.String(20), nullable=False),
            sa.Column("input_json", sa.JSON(), nullable=True),
            sa.Column("output_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("node_count", sa.Integer(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("started_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("started_at", sa.DateTime(), default=datetime.utcnow),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_workflow_runs_wf_started", "workflow_runs", ["workflow_id", "started_at"])

    # 3. Add new columns to workflows
    if not _has_column("workflows", "hub_id"):
        op.add_column("workflows", sa.Column("hub_id", sa.String(36), sa.ForeignKey("hubs.id", ondelete="CASCADE"), nullable=True))
        op.create_index(op.f("ix_workflows_hub_id"), "workflows", ["hub_id"], unique=False)
    if not _has_column("workflows", "slug"):
        op.add_column("workflows", sa.Column("slug", sa.String(120), nullable=True))
    if not _has_column("workflows", "description"):
        op.add_column("workflows", sa.Column("description", sa.Text(), nullable=True))
    if not _has_column("workflows", "tags_json"):
        op.add_column("workflows", sa.Column("tags_json", sa.JSON(), nullable=False, server_default="[]"))
    if not _has_column("workflows", "status"):
        op.add_column("workflows", sa.Column("status", sa.String(20), nullable=False, server_default="draft"))
    if not _has_column("workflows", "published_version_id"):
        op.add_column("workflows", sa.Column("published_version_id", sa.String(36), sa.ForeignKey("workflow_versions.id", ondelete="SET NULL"), nullable=True))
    if not _has_column("workflows", "draft_version_id"):
        op.add_column("workflows", sa.Column("draft_version_id", sa.String(36), sa.ForeignKey("workflow_versions.id", ondelete="SET NULL"), nullable=True))
    if not _has_column("workflows", "created_by"):
        op.add_column("workflows", sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))

    # 4. Add columns to eval_flow_traces
    if not _has_column("eval_flow_traces", "hub_id"):
        op.add_column("eval_flow_traces", sa.Column("hub_id", sa.String(36), sa.ForeignKey("hubs.id", ondelete="CASCADE"), nullable=True))
        op.create_index(op.f("ix_eval_flow_traces_hub_id"), "eval_flow_traces", ["hub_id"], unique=False)
    if not _has_column("eval_flow_traces", "eval_run_id"):
        op.add_column("eval_flow_traces", sa.Column("eval_run_id", sa.String(36), sa.ForeignKey("eval_run_history.id", ondelete="CASCADE"), nullable=True))
        op.create_index(op.f("ix_eval_flow_traces_eval_run_id"), "eval_flow_traces", ["eval_run_id"], unique=False)
    if not _has_column("eval_flow_traces", "sequence"):
        op.add_column("eval_flow_traces", sa.Column("sequence", sa.Integer(), nullable=True))

    # 5. Data backfill for workflows
    conn.execute(
        sa.text(
            """
            UPDATE workflows
            SET hub_id = COALESCE(
                hub_id,
                (SELECT id FROM hubs WHERE hub_type='workflow' AND slug='default' LIMIT 1),
                '00000000-0000-0000-0000-000000000003'
            )
            WHERE hub_id IS NULL;
            """
        )
    )

    # Slug backfill
    rows = conn.execute(sa.text("SELECT id, name, slug, hub_id FROM workflows WHERE slug IS NULL OR slug = ''")).fetchall()
    used_slugs: set[tuple[str, str]] = set()
    for row in rows:
        wf_id, name, current_slug, hub_id = row[0], row[1], row[2], row[3]
        base_slug = _slugify(name or "workflow")
        candidate = base_slug
        suffix = 1
        while (hub_id, candidate) in used_slugs:
            candidate = f"{base_slug}-{suffix}"
            suffix += 1
        used_slugs.add((hub_id, candidate))
        conn.execute(
            sa.text("UPDATE workflows SET slug = :slug WHERE id = :id"),
            {"slug": candidate, "id": wf_id},
        )

    # Version backfill from legacy graph_json if graph_json column exists
    if _has_column("workflows", "graph_json"):
        wf_rows = conn.execute(sa.text("SELECT id, graph_json FROM workflows")).fetchall()
        for wf_id, graph_json in wf_rows:
            # Check if version already exists
            v_exists = conn.execute(
                sa.text("SELECT id FROM workflow_versions WHERE workflow_id = :wf_id AND version_number = 1"),
                {"wf_id": wf_id},
            ).fetchone()
            if not v_exists:
                v_id = str(uuid.uuid4())
                graph_val = graph_json if graph_json is not None else {}
                if isinstance(graph_val, str):
                    import json
                    try:
                        graph_val = json.loads(graph_val)
                    except Exception:
                        graph_val = {}
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO workflow_versions (id, workflow_id, version_number, graph_json, change_note, is_valid, created_at)
                        VALUES (:id, :wf_id, 1, :graph_json, 'Migrated from V5', 1, :now)
                        """
                    ),
                    {"id": v_id, "wf_id": wf_id, "graph_json": sa.dialects.postgresql.JSON().result_processor(None, None)(graph_val) if hasattr(sa.dialects, "postgresql") else str(graph_val).replace("'", '"'), "now": datetime.utcnow()},
                )
                conn.execute(
                    sa.text(
                        """
                        UPDATE workflows
                        SET published_version_id = :v_id, draft_version_id = :v_id, status = 'published'
                        WHERE id = :wf_id
                        """
                    ),
                    {"v_id": v_id, "wf_id": wf_id},
                )

    # Enforce non-nullable hub_id and slug
    op.alter_column("workflows", "hub_id", nullable=False)
    op.alter_column("workflows", "slug", nullable=False)

    existing_unique = [u["name"] for u in _inspector().get_unique_constraints("workflows")]
    if "uq_workflows_hub_name" in existing_unique:
        try:
            op.drop_constraint("uq_workflows_hub_name", "workflows", type_="unique")
        except Exception:
            pass
    if "uq_workflows_hub_slug" not in existing_unique:
        try:
            op.create_unique_constraint("uq_workflows_hub_slug", "workflows", ["hub_id", "slug"])
        except Exception:
            pass

    # Drop legacy columns from workflows if present
    if _has_column("workflows", "graph_json"):
        op.drop_column("workflows", "graph_json")
    if _has_column("workflows", "is_active"):
        op.drop_column("workflows", "is_active")

    # Backfill eval_flow_traces.hub_id
    conn.execute(
        sa.text(
            """
            UPDATE eval_flow_traces
            SET hub_id = COALESCE(
                hub_id,
                (SELECT hub_id FROM workflows WHERE id = eval_flow_traces.workflow_id),
                (SELECT id FROM hubs WHERE hub_type='eval' AND slug='default' LIMIT 1),
                '00000000-0000-0000-0000-000000000004'
            )
            WHERE hub_id IS NULL;
            """
        )
    )
    op.alter_column("eval_flow_traces", "hub_id", nullable=False)


def downgrade() -> None:
    # Downgrade logic: restore graph_json / is_active columns, drop workflow_runs and workflow_versions
    if not _has_column("workflows", "graph_json"):
        op.add_column("workflows", sa.Column("graph_json", sa.JSON(), nullable=True))
    if not _has_column("workflows", "is_active"):
        op.add_column("workflows", sa.Column("is_active", sa.Boolean(), server_default=sa.text("false")))

    if _has_table("workflow_versions"):
        conn = op.get_bind()
        conn.execute(
            sa.text(
                """
                UPDATE workflows
                SET graph_json = (
                    SELECT graph_json FROM workflow_versions
                    WHERE workflow_id = workflows.id AND version_number = 1 LIMIT 1
                )
                """
            )
        )

    existing_unique = [u["name"] for u in _inspector().get_unique_constraints("workflows")]
    if "uq_workflows_hub_slug" in existing_unique:
        try:
            op.drop_constraint("uq_workflows_hub_slug", "workflows", type_="unique")
        except Exception:
            pass

    if _has_table("workflow_runs"):
        op.drop_table("workflow_runs")
    if _has_table("workflow_versions"):
        op.drop_table("workflow_versions")

    for col in ["published_version_id", "draft_version_id", "status", "tags_json", "description", "slug"]:
        if _has_column("workflows", col):
            op.drop_column("workflows", col)

    if _has_column("eval_flow_traces", "sequence"):
        op.drop_column("eval_flow_traces", "sequence")
    if _has_column("eval_flow_traces", "eval_run_id"):
        op.drop_index(op.f("ix_eval_flow_traces_eval_run_id"), table_name="eval_flow_traces")
        op.drop_column("eval_flow_traces", "eval_run_id")
    if _has_column("eval_flow_traces", "hub_id"):
        op.drop_index(op.f("ix_eval_flow_traces_hub_id"), table_name="eval_flow_traces")
        op.drop_column("eval_flow_traces", "hub_id")
