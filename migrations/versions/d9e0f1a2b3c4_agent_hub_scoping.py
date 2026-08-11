"""v6_agent_hub_scoping

Revision ID: d9e0f1a2b3c4
Revises: c7d8e9f0a1b2
Create Date: 2026-07-29 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e0f1a2b3c4'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f0a1b2'
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
    # 1. Add collection_bindings_json to agent_definitions if missing
    if not _has_column("agent_definitions", "collection_bindings_json"):
        op.add_column("agent_definitions", sa.Column("collection_bindings_json", sa.JSON(), nullable=True))

    # 2. Add hub_id to api_keys if missing
    if not _has_column("api_keys", "hub_id"):
        if op.get_bind().dialect.name != "sqlite":
            op.add_column("api_keys", sa.Column("hub_id", sa.String(36), sa.ForeignKey("hubs.id", ondelete="CASCADE"), nullable=True))
        else:
            op.add_column("api_keys", sa.Column("hub_id", sa.String(36), nullable=True))
        op.create_index(op.f("ix_api_keys_hub_id"), "api_keys", ["hub_id"], unique=False)

    # 3. Handle index on agent_definitions.endpoint_slug
    existing_indexes = [i["name"] for i in _inspector().get_indexes("agent_definitions")]
    if "ix_agent_definitions_endpoint_slug" in existing_indexes:
        op.drop_index("ix_agent_definitions_endpoint_slug", table_name="agent_definitions")

    existing_unique = [u["name"] for u in _inspector().get_unique_constraints("agent_definitions")]
    if "uq_agent_definitions_hub_slug" not in existing_unique:
        try:
            if op.get_bind().dialect.name != "sqlite":
                op.create_unique_constraint("uq_agent_definitions_hub_slug", "agent_definitions", ["hub_id", "endpoint_slug"])
            else:
                with op.batch_alter_table("agent_definitions") as batch_op:
                    batch_op.create_unique_constraint("uq_agent_definitions_hub_slug", ["hub_id", "endpoint_slug"])
        except Exception:
            pass


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        existing_unique = [u["name"] for u in _inspector().get_unique_constraints("agent_definitions")]
        if "uq_agent_definitions_hub_slug" in existing_unique:
            try:
                op.drop_constraint("uq_agent_definitions_hub_slug", "agent_definitions", type_="unique")
            except Exception:
                pass
    else:
        try:
            with op.batch_alter_table("agent_definitions") as batch_op:
                batch_op.drop_constraint("uq_agent_definitions_hub_slug", type_="unique")
        except Exception:
            pass

    if _has_column("api_keys", "hub_id"):
        op.drop_index(op.f("ix_api_keys_hub_id"), table_name="api_keys")
        op.drop_column("api_keys", "hub_id")

    if _has_column("agent_definitions", "collection_bindings_json"):
        op.drop_column("agent_definitions", "collection_bindings_json")
