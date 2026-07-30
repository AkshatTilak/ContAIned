"""v6_workflow_reference_rewrite

Revision ID: e2f3a4b5c6d7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-30 12:00:00.000000

"""
import json
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    cols = [c["name"] for c in _inspector().get_columns(table)]
    return column in cols


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Resolve default hub IDs
    workflow_hub_id = conn.execute(
        sa.text("SELECT id FROM hubs WHERE hub_type='workflow' AND slug='default' LIMIT 1")
    ).scalar() or "00000000-0000-0000-0000-0000000000a3"

    agent_hub_id = conn.execute(
        sa.text("SELECT id FROM hubs WHERE hub_type='agent' AND slug='default' LIMIT 1")
    ).scalar() or "00000000-0000-0000-0000-0000000000a2"

    ingestion_hub_id = conn.execute(
        sa.text("SELECT id FROM hubs WHERE hub_type='ingestion' AND slug='default' LIMIT 1")
    ).scalar() or "00000000-0000-0000-0000-0000000000a1"

    # 2. Seed hub links if missing
    if _has_table("hub_links"):
        # workflow -> agent link
        wf_agent_link = conn.execute(
            sa.text(
                "SELECT id FROM hub_links WHERE source_hub_id = :src AND target_hub_id = :tgt"
            ),
            {"src": workflow_hub_id, "tgt": agent_hub_id},
        ).scalar()
        if not wf_agent_link:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO hub_links (id, source_hub_id, target_hub_id, access_level, created_at)
                    VALUES (:id, :src, :tgt, 'use', :now)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "src": workflow_hub_id,
                    "tgt": agent_hub_id,
                    "now": datetime.utcnow(),
                },
            )

        # workflow -> ingestion link
        wf_ingest_link = conn.execute(
            sa.text(
                "SELECT id FROM hub_links WHERE source_hub_id = :src AND target_hub_id = :tgt"
            ),
            {"src": workflow_hub_id, "tgt": ingestion_hub_id},
        ).scalar()
        if not wf_ingest_link:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO hub_links (id, source_hub_id, target_hub_id, access_level, created_at)
                    VALUES (:id, :src, :tgt, 'read', :now)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "src": workflow_hub_id,
                    "tgt": ingestion_hub_id,
                    "now": datetime.utcnow(),
                },
            )

    # 3. Rewrite graph_json references in workflow_versions
    if _has_table("workflow_versions"):
        rows = conn.execute(sa.text("SELECT id, graph_json FROM workflow_versions")).fetchall()
        versions_scanned = 0
        refs_rewritten = 0
        refs_unresolved = 0

        for version_id, raw_graph in rows:
            versions_scanned += 1
            graph_json = raw_graph
            if isinstance(graph_json, str):
                try:
                    graph_json = json.loads(graph_json)
                except Exception:
                    graph_json = {}
            if not isinstance(graph_json, dict):
                graph_json = {}

            nodes = graph_json.get("nodes", [])
            modified = False
            has_unresolved = False

            for node in nodes:
                node_type = node.get("type", "")
                data = node.get("data")
                if not isinstance(data, dict):
                    continue

                # AgentNode
                if node_type in ("AgentNode", "agent"):
                    agent_id = data.get("agent_id") or data.get("agent")
                    if agent_id and "reference" not in data:
                        data["reference"] = {
                            "type": "agent",
                            "hub_id": agent_hub_id,
                            "resource_id": str(agent_id),
                        }
                        data.pop("agent_id", None)
                        data.pop("agent", None)
                        modified = True
                        refs_rewritten += 1

                # RetrievalNode
                elif node_type in ("RetrievalNode", "retrieval"):
                    coll_val = data.get("collection") or data.get("collection_name")
                    if coll_val and "reference" not in data:
                        # Find collection ID by name or ID
                        coll_id = None
                        if _has_table("syntraflow_collections"):
                            c_row = conn.execute(
                                sa.text(
                                    "SELECT id FROM syntraflow_collections WHERE (id = :val OR name = :val) LIMIT 1"
                                ),
                                {"val": str(coll_val)},
                            ).fetchone()
                            if c_row:
                                coll_id = c_row[0]

                        if coll_id:
                            data["reference"] = {
                                "type": "collection",
                                "hub_id": ingestion_hub_id,
                                "resource_id": str(coll_id),
                            }
                            data.pop("collection", None)
                            data.pop("collection_name", None)
                            modified = True
                            refs_rewritten += 1
                        else:
                            has_unresolved = True
                            refs_unresolved += 1

                # MultiAgentNode
                elif node_type in ("MultiAgentNode",):
                    agents_list = data.get("agents")
                    if isinstance(agents_list, list) and "references" not in data:
                        new_refs = []
                        for aitem in agents_list:
                            a_id = aitem if isinstance(aitem, str) else (aitem.get("id") or aitem.get("agent_id") if isinstance(aitem, dict) else str(aitem))
                            if a_id:
                                new_refs.append({
                                    "type": "agent",
                                    "hub_id": agent_hub_id,
                                    "resource_id": str(a_id),
                                })
                        data["references"] = new_refs
                        data.pop("agents", None)
                        modified = True
                        refs_rewritten += len(new_refs)

            if modified or has_unresolved:
                dumped_graph = json.dumps(graph_json)
                if has_unresolved:
                    validation_val = json.dumps({
                        "errors": [{
                            "code": "MIGRATION_UNRESOLVED_REFERENCE",
                            "message": "One or more node references could not be resolved during migration"
                        }]
                    })
                    conn.execute(
                        sa.text(
                            "UPDATE workflow_versions SET graph_json = :g, validation_json = :v, is_valid = false WHERE id = :id"
                        ),
                        {"g": dumped_graph, "v": validation_val, "id": version_id},
                    )
                else:
                    conn.execute(
                        sa.text("UPDATE workflow_versions SET graph_json = :g WHERE id = :id"),
                        {"g": dumped_graph, "id": version_id},
                    )

        # Audit log entry
        if _has_table("audit_log"):
            actor_col = "actor_user_id" if _has_column("audit_log", "actor_user_id") else ("actor_id" if _has_column("audit_log", "actor_id") else "user_id")
            summary_col = "summary" if _has_column("audit_log", "summary") else "details_json"
            conn.execute(
                sa.text(
                    f"""
                    INSERT INTO audit_log (id, hub_id, {actor_col}, action, resource_type, resource_id, {summary_col}, created_at)
                    VALUES (:id, :hub_id, NULL, 'migrate', 'workflow', :wf_hub_id, :details, :now)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "hub_id": workflow_hub_id,
                    "wf_hub_id": workflow_hub_id,
                    "details": json.dumps({
                        "versions_scanned": versions_scanned,
                        "refs_rewritten": refs_rewritten,
                        "refs_unresolved": refs_unresolved,
                    }),
                    "now": datetime.utcnow(),
                },
            )


def downgrade() -> None:
    conn = op.get_bind()
    if _has_table("workflow_versions"):
        rows = conn.execute(sa.text("SELECT id, graph_json FROM workflow_versions")).fetchall()
        for version_id, raw_graph in rows:
            graph_json = raw_graph
            if isinstance(graph_json, str):
                try:
                    graph_json = json.loads(graph_json)
                except Exception:
                    graph_json = {}
            if not isinstance(graph_json, dict):
                continue

            nodes = graph_json.get("nodes", [])
            modified = False

            for node in nodes:
                node_type = node.get("type", "")
                data = node.get("data")
                if not isinstance(data, dict):
                    continue

                if node_type in ("AgentNode", "agent"):
                    ref = data.get("reference")
                    if isinstance(ref, dict) and ref.get("resource_id"):
                        data["agent_id"] = ref["resource_id"]
                        data.pop("reference", None)
                        modified = True

                elif node_type in ("RetrievalNode", "retrieval"):
                    ref = data.get("reference")
                    if isinstance(ref, dict) and ref.get("resource_id"):
                        data["collection"] = ref["resource_id"]
                        data.pop("reference", None)
                        modified = True

                elif node_type in ("MultiAgentNode",):
                    refs = data.get("references")
                    if isinstance(refs, list):
                        data["agents"] = [r.get("resource_id") for r in refs if isinstance(r, dict) and r.get("resource_id")]
                        data.pop("references", None)
                        modified = True

            if modified:
                conn.execute(
                    sa.text("UPDATE workflow_versions SET graph_json = :g WHERE id = :id"),
                    {"g": json.dumps(graph_json), "id": version_id},
                )
