import os
import tempfile
import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic import command


@pytest.fixture
def temp_db_config():
    """Create a temporary SQLite database and return Alembic Config pointed to it."""
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    db_path = db_file.name
    db_url = f"sqlite:///{db_path}"

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)

    yield config, db_url, db_path

    # Cleanup temporary database file
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_stage1_migration_upgrade_and_downgrade(temp_db_config):
    config, db_url, _ = temp_db_config

    # Upgrade to Stage 1 revision: a6b1c2d3e4f5
    command.upgrade(config, "a6b1c2d3e4f5")

    engine = sa.create_engine(db_url)
    inspector = sa.inspect(engine)

    # 1. Assert five new tenancy tables exist
    new_tables = ["hubs", "hub_members", "hub_links", "datastore_bindings", "audit_log"]
    table_names = inspector.get_table_names()
    for table in new_tables:
        assert table in table_names, f"Table '{table}' missing after stage 1 upgrade"

    # 2. Assert 14 target tables have nullable hub_id column
    hub_id_tables = [
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
    for table in hub_id_tables:
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        assert "hub_id" in cols, f"'hub_id' missing from table '{table}'"
        assert cols["hub_id"]["nullable"] is True, f"'hub_id' in table '{table}' should be nullable in stage 1"

    # 3. Assert legacy columns are still present
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    assert "role" in user_cols, "'users.role' must remain in stage 1"
    assert "platform_role" in user_cols, "'users.platform_role' must be added in stage 1"

    collection_cols = {c["name"] for c in inspector.get_columns("syntraflow_collections")}
    assert "tenant_id" in collection_cols, "'syntraflow_collections.tenant_id' must remain in stage 1"
    assert "physical_name" in collection_cols, "'syntraflow_collections.physical_name' must be added in stage 1"

    # 4. Test idempotency: Upgrade head again should be a no-op
    command.upgrade(config, "a6b1c2d3e4f5")

    # 5. Test downgrade to f6f7a8b9c0d1
    command.downgrade(config, "f6f7a8b9c0d1")
    inspector = sa.inspect(engine)
    table_names = inspector.get_table_names()

    for table in new_tables:
        assert table not in table_names, f"Table '{table}' should be dropped after downgrade"

    for table in hub_id_tables:
        if table in table_names:
            cols = {c["name"] for c in inspector.get_columns(table)}
            assert "hub_id" not in cols, f"'hub_id' should be dropped from table '{table}' after downgrade"

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    assert "platform_role" not in user_cols, "'users.platform_role' should be dropped after downgrade"

    engine.dispose()