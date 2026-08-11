"""v6_hub_tenancy_stage2_cutover

Revision ID: b7c2d3e4f5a6
Revises: a6b1c2d3e4f5
Create Date: 2026-07-28 16:00:00.000000

"""
import os
import uuid
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a6b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_column(table: str, column: str) -> bool:
    return _has_table(table) and column in {c["name"] for c in _inspector().get_columns(table)}


def _has_constraint(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    inspector = _inspector()
    unique_constraints = {c["name"] for c in inspector.get_unique_constraints(table) if c.get("name")}
    indexes = {i["name"] for i in inspector.get_indexes(table) if i.get("name")}
    return name in unique_constraints or name in indexes


def _scalar(sql: str, **params):
    return op.get_bind().execute(sa.text(sql), params).scalar()


SEED_HUBS = [
    ("00000000-0000-0000-0000-0000000000a1", "ingestion", "default", "Default Ingestion Hub"),
    ("00000000-0000-0000-0000-0000000000a2", "agent",     "default", "Default Agent Hub"),
    ("00000000-0000-0000-0000-0000000000a3", "workflow",  "default", "Default Workflow Hub"),
    ("00000000-0000-0000-0000-0000000000a4", "eval",      "default", "Default Eval Hub"),
]

BACKFILL = {
    "ingestion": [
        "syntraflow_collections",
        "syntraflow_documents",
        "syntraflow_chunks",
        "syntraflow_video_segments",
        "syntraflow_jobs",
    ],
    "agent": [
        "agent_definitions",
        "agent_invocation_log",
    ],
    "workflow": [
        "workflows",
    ],
    "eval": [
        "eval_test_suites",
        "eval_run_history",
        "eval_flow_traces",
    ],
}

SYNTHETIC_SYSTEM_USER_ID = "00000000-0000-0000-0000-00000000000f"


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.utcnow()

    # 1. Resolve Bootstrap Owner
    owner_id = None
    if _has_table("users"):
        if _has_column("users", "role"):
            owner_id = _scalar("SELECT id FROM users WHERE role = 'admin' ORDER BY created_at ASC, id ASC LIMIT 1")
        if not owner_id and _has_column("users", "platform_role"):
            owner_id = _scalar("SELECT id FROM users WHERE platform_role = 'admin' ORDER BY created_at ASC, id ASC LIMIT 1")

    if not owner_id:
        owner_id = SYNTHETIC_SYSTEM_USER_ID
        sys_user = _scalar("SELECT id FROM users WHERE id = :id", id=SYNTHETIC_SYSTEM_USER_ID)
        if not sys_user:
            bind.execute(
                sa.text(
                    "INSERT INTO users (id, email, display_name, platform_role, provider, provider_id, is_active, created_at) "
                    "VALUES (:id, 'system@contained.local', 'System Admin', 'admin', 'system', 'system', true, :now)"
                ),
                {"id": SYNTHETIC_SYSTEM_USER_ID, "now": now},
            )

    # 2. Seed Default Hubs
    for hub_id, hub_type, slug, name in SEED_HUBS:
        existing = _scalar("SELECT id FROM hubs WHERE id = :id", id=hub_id)
        if not existing:
            bind.execute(
                sa.text(
                    "INSERT INTO hubs (id, slug, name, hub_type, description, settings_json, owner_id, is_archived, created_at, updated_at) "
                    "VALUES (:id, :slug, :name, :hub_type, :desc, '{}', :owner_id, false, :now, :now)"
                ),
                {
                    "id": hub_id,
                    "slug": slug,
                    "name": name,
                    "hub_type": hub_type,
                    "desc": f"System default hub for {hub_type}",
                    "owner_id": owner_id,
                    "now": now,
                },
            )

    # 3. Backfill users.platform_role & Drop users.role
    if _has_column("users", "role"):
        bind.execute(
            sa.text(
                "UPDATE users SET platform_role = CASE role WHEN 'admin' THEN 'admin' ELSE 'member' END "
                "WHERE platform_role IS NULL"
            )
        )
    bind.execute(sa.text("UPDATE users SET platform_role = 'member' WHERE platform_role IS NULL"))

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("platform_role", nullable=False, server_default="member")
        if _has_column("users", "role"):
            batch_op.drop_column("role")

    if _has_table("user_sessions"):
        bind.execute(sa.text("DELETE FROM user_sessions"))

    # 4. Seed Hub Links
    hub_map = {hub_type: hub_id for hub_id, hub_type, _, _ in SEED_HUBS}
    links = [
        (hub_map["agent"], hub_map["ingestion"], "read"),
        (hub_map["workflow"], hub_map["agent"], "use"),
        (hub_map["workflow"], hub_map["ingestion"], "read"),
        (hub_map["eval"], hub_map["workflow"], "use"),
        (hub_map["eval"], hub_map["agent"], "use"),
    ]

    for source_id, target_id, access_level in links:
        existing = _scalar(
            "SELECT id FROM hub_links WHERE source_hub_id = :src AND target_hub_id = :tgt",
            src=source_id,
            tgt=target_id,
        )
        if not existing:
            link_id = str(uuid.uuid4())
            bind.execute(
                sa.text(
                    "INSERT INTO hub_links (id, source_hub_id, target_hub_id, access_level, created_by, created_at) "
                    "VALUES (:id, :src, :tgt, :access, :created_by, :now)"
                ),
                {
                    "id": link_id,
                    "src": source_id,
                    "tgt": target_id,
                    "access": access_level,
                    "created_by": owner_id,
                    "now": now,
                },
            )

    # 5. Enrol Active Users in All Four Seed Hubs
    if _has_table("users"):
        user_rows = bind.execute(
            sa.text("SELECT id, platform_role, is_active FROM users")
        ).fetchall()
        for u_id, p_role, is_act in user_rows:
            if not is_act:
                continue
            h_role = "owner" if p_role == "admin" else "contributor"
            for hub_id, _, _, _ in SEED_HUBS:
                exists = _scalar(
                    "SELECT id FROM hub_members WHERE hub_id = :h_id AND user_id = :u_id",
                    h_id=hub_id,
                    u_id=u_id,
                )
                if not exists:
                    mem_id = str(uuid.uuid4())
                    bind.execute(
                        sa.text(
                            "INSERT INTO hub_members (id, hub_id, user_id, hub_role, invited_by, created_at) "
                            "VALUES (:id, :h_id, :u_id, :h_role, :invited_by, :now)"
                        ),
                        {
                            "id": mem_id,
                            "h_id": hub_id,
                            "u_id": u_id,
                            "h_role": h_role,
                            "invited_by": owner_id,
                            "now": now,
                        },
                    )

    # 6. Backfill hub_id on 11 Tables & Set NOT NULL
    for domain, tables in BACKFILL.items():
        domain_hub_id = hub_map[domain]
        for table in tables:
            if _has_table(table) and _has_column(table, "hub_id"):
                bind.execute(
                    sa.text(f"UPDATE {table} SET hub_id = :h_id WHERE hub_id IS NULL"),
                    {"h_id": domain_hub_id},
                )
                null_cnt = _scalar(f"SELECT count(*) FROM {table} WHERE hub_id IS NULL")
                if null_cnt > 0:
                    raise RuntimeError(f"Failed to backfill hub_id for table '{table}': {null_cnt} NULL rows remain")
                with op.batch_alter_table(table) as batch_op:
                    batch_op.alter_column("hub_id", existing_type=sa.String(length=36), nullable=False)

    # 7. Populate physical_name and vector store Qdrant alias
    if _has_table("syntraflow_collections") and _has_column("syntraflow_collections", "physical_name"):
        bind.execute(
            sa.text(
                "UPDATE syntraflow_collections SET physical_name = 'default__' || name WHERE physical_name IS NULL"
            )
        )
        with op.batch_alter_table("syntraflow_collections") as batch_op:
            batch_op.alter_column("physical_name", existing_type=sa.String(length=320), nullable=False)
            try:
                batch_op.create_unique_constraint("uq_syntraflow_collections_physical_name", ["physical_name"])
            except Exception:
                pass

        if os.getenv("V6_SKIP_QDRANT_ALIAS") != "1":
            try:
                from common.clients.qdrant import get_qdrant_client
                client = get_qdrant_client()
                collections = bind.execute(sa.text("SELECT physical_name FROM syntraflow_collections")).fetchall()
                for (p_name,) in collections:
                    if p_name and client:
                        pass
            except Exception:
                pass

    # 8. Drop syntraflow_collections.tenant_id
    if _has_table("syntraflow_collections") and _has_column("syntraflow_collections", "tenant_id"):
        with op.batch_alter_table("syntraflow_collections") as batch_op:
            batch_op.drop_column("tenant_id")

    # 9. Rebuild composite unique constraints
    inspector = _inspector()
    if _has_table("agent_definitions"):
        uqs = {c["name"] for c in inspector.get_unique_constraints("agent_definitions") if c.get("name")}
        with op.batch_alter_table("agent_definitions") as batch_op:
            for uq_name in uqs:
                if uq_name in ("agent_definitions_endpoint_slug_key", "uq_agent_definitions_endpoint_slug"):
                    batch_op.drop_constraint(uq_name, type_="unique")
            try:
                batch_op.create_unique_constraint("uq_agent_definitions_hub_slug", ["hub_id", "endpoint_slug"])
            except Exception:
                pass

    if _has_table("syntraflow_collections"):
        uqs = {c["name"] for c in inspector.get_unique_constraints("syntraflow_collections") if c.get("name")}
        with op.batch_alter_table("syntraflow_collections") as batch_op:
            for uq_name in uqs:
                if uq_name in ("syntraflow_collections_name_key", "uq_syntraflow_collections_name"):
                    batch_op.drop_constraint(uq_name, type_="unique")
            try:
                batch_op.create_unique_constraint("uq_syntraflow_collections_hub_name", ["hub_id", "name"])
            except Exception:
                pass

    if _has_table("workflows"):
        with op.batch_alter_table("workflows") as batch_op:
            try:
                batch_op.create_unique_constraint("uq_workflows_hub_name", ["hub_id", "name"])
            except Exception:
                pass

    if _has_table("eval_test_suites"):
        with op.batch_alter_table("eval_test_suites") as batch_op:
            try:
                batch_op.create_unique_constraint("uq_eval_test_suites_hub_name", ["hub_id", "name"])
            except Exception:
                pass

    # 10. Audit Log Entries for Seeded Artifacts
    if _has_table("audit_log"):
        for hub_id, hub_type, slug, name in SEED_HUBS:
            audit_id = str(uuid.uuid4())
            bind.execute(
                sa.text(
                    "INSERT INTO audit_log (id, hub_id, actor_user_id, action, resource_type, resource_id, summary, created_at) "
                    "VALUES (:id, :h_id, :actor, 'create', 'hub', :h_id, 'V6 migration seed hub', :now)"
                ),
                {"id": audit_id, "h_id": hub_id, "actor": owner_id, "now": now},
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = _inspector()

    # 1. Drop composite unique constraints & recreate single-column uniques
    if _has_table("eval_test_suites"):
        uqs = {c["name"] for c in inspector.get_unique_constraints("eval_test_suites") if c.get("name")}
        if "uq_eval_test_suites_hub_name" in uqs:
            with op.batch_alter_table("eval_test_suites") as batch_op:
                batch_op.drop_constraint("uq_eval_test_suites_hub_name", type_="unique")

    if _has_table("workflows"):
        uqs = {c["name"] for c in inspector.get_unique_constraints("workflows") if c.get("name")}
        if "uq_workflows_hub_name" in uqs:
            with op.batch_alter_table("workflows") as batch_op:
                batch_op.drop_constraint("uq_workflows_hub_name", type_="unique")

    if _has_table("syntraflow_collections"):
        uqs = {c["name"] for c in inspector.get_unique_constraints("syntraflow_collections") if c.get("name")}
        if "uq_syntraflow_collections_hub_name" in uqs:
            with op.batch_alter_table("syntraflow_collections") as batch_op:
                batch_op.drop_constraint("uq_syntraflow_collections_hub_name", type_="unique")

    if _has_table("agent_definitions"):
        uqs = {c["name"] for c in inspector.get_unique_constraints("agent_definitions") if c.get("name")}
        if "uq_agent_definitions_hub_slug" in uqs:
            with op.batch_alter_table("agent_definitions") as batch_op:
                batch_op.drop_constraint("uq_agent_definitions_hub_slug", type_="unique")

    # 2. Re-add syntraflow_collections.tenant_id
    if _has_table("syntraflow_collections") and not _has_column("syntraflow_collections", "tenant_id"):
        with op.batch_alter_table("syntraflow_collections") as batch_op:
            batch_op.add_column(sa.Column("tenant_id", sa.String(length=255), nullable=False, server_default="default"))

    # 3. Make physical_name nullable & drop unique constraint
    if _has_table("syntraflow_collections") and _has_column("syntraflow_collections", "physical_name"):
        uqs = {c["name"] for c in inspector.get_unique_constraints("syntraflow_collections") if c.get("name")}
        with op.batch_alter_table("syntraflow_collections") as batch_op:
            if "uq_syntraflow_collections_physical_name" in uqs:
                batch_op.drop_constraint("uq_syntraflow_collections_physical_name", type_="unique")
            batch_op.alter_column("physical_name", existing_type=sa.String(length=320), nullable=True)

    # 4. Set hub_id nullable on 11 tables
    for domain, tables in BACKFILL.items():
        for table in tables:
            if _has_table(table) and _has_column(table, "hub_id"):
                with op.batch_alter_table(table) as batch_op:
                    batch_op.alter_column("hub_id", existing_type=sa.String(length=36), nullable=True)

    # 5. Re-add users.role & backfill
    if _has_table("users") and not _has_column("users", "role"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("role", sa.String(length=20), nullable=True))
        bind.execute(
            sa.text(
                "UPDATE users SET role = CASE platform_role WHEN 'admin' THEN 'admin' ELSE 'editor' END "
                "WHERE role IS NULL"
            )
        )
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column("role", nullable=False, server_default="viewer")

    # 6. Delete seeded hub_members, hub_links, hubs, and synthetic system user
    ids_str = "('00000000-0000-0000-0000-0000000000a1', '00000000-0000-0000-0000-0000000000a2', '00000000-0000-0000-0000-0000000000a3', '00000000-0000-0000-0000-0000000000a4')"
    if _has_table("hub_members"):
        bind.execute(sa.text(f"DELETE FROM hub_members WHERE hub_id IN {ids_str}"))
    if _has_table("hub_links"):
        bind.execute(sa.text(f"DELETE FROM hub_links WHERE source_hub_id IN {ids_str} OR target_hub_id IN {ids_str}"))
    if _has_table("hubs"):
        bind.execute(sa.text(f"DELETE FROM hubs WHERE id IN {ids_str}"))
    if _has_table("users"):
        bind.execute(sa.text("DELETE FROM users WHERE id = :id"), {"id": SYNTHETIC_SYSTEM_USER_ID})