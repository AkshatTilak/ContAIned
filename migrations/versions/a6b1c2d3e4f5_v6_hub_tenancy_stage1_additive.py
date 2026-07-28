"""v6_hub_tenancy_stage1_additive

Revision ID: a6b1c2d3e4f5
Revises: f6f7a8b9c0d1
Create Date: 2026-07-28 15:38:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6b1c2d3e4f5'
down_revision: Union[str, Sequence[str], None] = 'f6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_column(table: str, column: str) -> bool:
    return _has_table(table) and column in {c["name"] for c in _inspector().get_columns(table)}


HUB_ID_TABLES = [
    "syntraflow_collections",
    "syntraflow_documents",
    "syntraflow_chunks",
    "syntraflow_video_segments",
    "syntraflow_jobs",
    "agent_definitions",
    "agent_invocation_log",
    "workflows",
    "eval_test_suites",
    "eval_run_history",
    "eval_flow_traces",
    "api_keys",
    "mcp_servers",
    "playground_sessions",
]


def upgrade() -> None:
    # 1. hubs
    if not _has_table("hubs"):
        op.create_table(
            "hubs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("hub_type", sa.String(length=20), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("accent", sa.String(length=20), nullable=True),
            sa.Column("icon", sa.String(length=40), nullable=True),
            sa.Column("settings_json", sa.JSON(), nullable=False),
            sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("hub_type", "slug", name="uq_hubs_type_slug")
        )
        op.create_index("ix_hubs_slug", "hubs", ["slug"], unique=False)
        op.create_index("ix_hubs_hub_type", "hubs", ["hub_type"], unique=False)
        op.create_index("ix_hubs_owner_id", "hubs", ["owner_id"], unique=False)
        op.create_index("ix_hubs_is_archived", "hubs", ["is_archived"], unique=False)

    # 2. hub_members
    if not _has_table("hub_members"):
        op.create_table(
            "hub_members",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("hub_id", sa.String(length=36), sa.ForeignKey("hubs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("hub_role", sa.String(length=20), nullable=False),
            sa.Column("invited_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("hub_id", "user_id", name="uq_hub_members_hub_user")
        )
        op.create_index("ix_hub_members_hub_id", "hub_members", ["hub_id"], unique=False)
        op.create_index("ix_hub_members_user_id", "hub_members", ["user_id"], unique=False)
        op.create_index("ix_hub_members_user_hub", "hub_members", ["user_id", "hub_id"], unique=False)

    # 3. hub_links
    if not _has_table("hub_links"):
        op.create_table(
            "hub_links",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("source_hub_id", sa.String(length=36), sa.ForeignKey("hubs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("target_hub_id", sa.String(length=36), sa.ForeignKey("hubs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("access_level", sa.String(length=20), nullable=False, server_default="read"),
            sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_hub_id", "target_hub_id", name="uq_hub_links_source_target")
        )
        op.create_index("ix_hub_links_source_hub_id", "hub_links", ["source_hub_id"], unique=False)
        op.create_index("ix_hub_links_target_hub_id", "hub_links", ["target_hub_id"], unique=False)

    # 4. datastore_bindings
    if not _has_table("datastore_bindings"):
        op.create_table(
            "datastore_bindings",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("hub_id", sa.String(length=36), sa.ForeignKey("hubs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("store_type", sa.String(length=20), nullable=False),
            sa.Column("connection_uri", sa.String(length=500), nullable=False),
            sa.Column("credentials_encrypted", sa.Text(), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("health_status", sa.String(length=20), nullable=False, server_default="unknown"),
            sa.Column("last_health_check", sa.DateTime(), nullable=True),
            sa.Column("config_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("hub_id", "name", name="uq_datastore_bindings_hub_name")
        )
        op.create_index("ix_datastore_bindings_hub_id", "datastore_bindings", ["hub_id"], unique=False)
        op.create_index("ix_datastore_bindings_hub_store_type", "datastore_bindings", ["hub_id", "store_type"], unique=False)

    # 5. audit_log
    if not _has_table("audit_log"):
        op.create_table(
            "audit_log",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("hub_id", sa.String(length=36), sa.ForeignKey("hubs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("actor_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action", sa.String(length=40), nullable=False),
            sa.Column("resource_type", sa.String(length=40), nullable=False),
            sa.Column("resource_id", sa.String(length=36), nullable=True),
            sa.Column("summary", sa.String(length=255), nullable=True),
            sa.Column("before_json", sa.JSON(), nullable=True),
            sa.Column("after_json", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id")
        )
        op.create_index("ix_audit_log_hub_id", "audit_log", ["hub_id"], unique=False)
        op.create_index("ix_audit_log_actor_user_id", "audit_log", ["actor_user_id"], unique=False)
        op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"], unique=False)
        op.create_index("ix_audit_log_hub_created", "audit_log", ["hub_id", "created_at"], unique=False)
        op.create_index("ix_audit_log_resource", "audit_log", ["resource_type", "resource_id"], unique=False)

    # 6. Propagate hub_id FKs to domain tables
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    for table in HUB_ID_TABLES:
        if _has_table(table) and not _has_column(table, "hub_id"):
            op.add_column(table, sa.Column("hub_id", sa.String(length=36), nullable=True))
            op.create_index(f"ix_{table}_hub_id", table, ["hub_id"], unique=False)
            if not is_sqlite:
                op.create_foreign_key(
                    f"fk_{table}_hub_id", table, "hubs", ["hub_id"], ["id"], ondelete="CASCADE"
                )

    # 7. syntraflow_collections.physical_name
    if _has_table("syntraflow_collections") and not _has_column("syntraflow_collections", "physical_name"):
        op.add_column("syntraflow_collections", sa.Column("physical_name", sa.String(length=300), nullable=True))
        op.create_index("ix_syntraflow_collections_physical_name", "syntraflow_collections", ["physical_name"], unique=False)

    # 8. users.platform_role
    if _has_table("users") and not _has_column("users", "platform_role"):
        op.add_column("users", sa.Column("platform_role", sa.String(length=20), nullable=True))


def downgrade() -> None:
    # 1. users.platform_role
    if _has_column("users", "platform_role"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("platform_role")

    # 2. syntraflow_collections.physical_name
    if _has_column("syntraflow_collections", "physical_name"):
        with op.batch_alter_table("syntraflow_collections") as batch_op:
            try:
                batch_op.drop_index("ix_syntraflow_collections_physical_name")
            except Exception:
                pass
            batch_op.drop_column("physical_name")

    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 3. HUB_ID_TABLES
    for table in reversed(HUB_ID_TABLES):
        if _has_column(table, "hub_id"):
            with op.batch_alter_table(table) as batch_op:
                if not is_sqlite:
                    try:
                        batch_op.drop_constraint(f"fk_{table}_hub_id", type_="foreignkey")
                    except Exception:
                        pass
                try:
                    batch_op.drop_index(f"ix_{table}_hub_id")
                except Exception:
                    pass
                batch_op.drop_column("hub_id")

    # 4. New tenancy tables (reverse FK order)
    for table in ["audit_log", "datastore_bindings", "hub_links", "hub_members", "hubs"]:
        if _has_table(table):
            op.drop_table(table)
