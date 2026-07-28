import os
import uuid
import tempfile
import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic import command


@pytest.fixture
def temp_db_v5():
    """Create a temporary SQLite database, run migrations up to Stage 1, and seed V5 legacy data."""
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    db_path = db_file.name
    db_url = f"sqlite:///{db_path}"

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)

    # Upgrade to Stage 1 additive schema: a6b1c2d3e4f5
    command.upgrade(config, "a6b1c2d3e4f5")

    engine = sa.create_engine(db_url)
    with engine.begin() as conn:
        # Seed 3 Users with V5 roles
        u1_id = str(uuid.uuid4())
        u2_id = str(uuid.uuid4())
        u3_id = str(uuid.uuid4())

        conn.execute(
            sa.text(
                "INSERT INTO users (id, email, display_name, role, provider, provider_id, is_active) "
                "VALUES (:id, 'admin@contained.local', 'Admin User', 'admin', 'local', 'admin1', true)"
            ),
            {"id": u1_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO users (id, email, display_name, role, provider, provider_id, is_active) "
                "VALUES (:id, 'editor@contained.local', 'Editor User', 'editor', 'local', 'editor1', true)"
            ),
            {"id": u2_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO users (id, email, display_name, role, provider, provider_id, is_active) "
                "VALUES (:id, 'viewer@contained.local', 'Viewer User', 'viewer', 'local', 'viewer1', true)"
            ),
            {"id": u3_id},
        )

        # Seed 2 Collections
        col1_id = str(uuid.uuid4())
        col2_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO syntraflow_collections (id, name, tenant_id) "
                "VALUES (:id, 'collection_alpha', 'default')"
            ),
            {"id": col1_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO syntraflow_collections (id, name, tenant_id) "
                "VALUES (:id, 'collection_beta', 'default')"
            ),
            {"id": col2_id},
        )

        # Seed 2 Agents
        agent1_id = str(uuid.uuid4())
        agent2_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO agent_definitions (id, name, role, system_prompt, model_id, endpoint_slug) "
                "VALUES (:id, 'Agent One', 'assistant', 'Prompt 1', 'gpt-4o', 'agent-one')"
            ),
            {"id": agent1_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO agent_definitions (id, name, role, system_prompt, model_id, endpoint_slug) "
                "VALUES (:id, 'Agent Two', 'assistant', 'Prompt 2', 'gpt-4o', 'agent-two')"
            ),
            {"id": agent2_id},
        )

        # Seed 1 Workflow
        wf1_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO workflows (id, name, graph_json, is_active) "
                "VALUES (:id, 'Workflow Main', '{}', true)"
            ),
            {"id": wf1_id},
        )

        # Seed 1 Eval Test Suite
        eval1_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO eval_test_suites (id, name, description, agent_id) "
                "VALUES (:id, 'Eval Suite 1', 'Test suite 1', :agent_id)"
            ),
            {"id": eval1_id, "agent_id": agent1_id},
        )

    engine.dispose()

    yield config, db_url, db_path

    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_stage2_cutover_migration_end_to_end(temp_db_v5):
    config, db_url, _ = temp_db_v5
    os.environ["V6_SKIP_QDRANT_ALIAS"] = "1"

    # Run Stage 2 Cutover migration upgrade: b7c2d3e4f5a6
    command.upgrade(config, "b7c2d3e4f5a6")

    engine = sa.create_engine(db_url)
    inspector = sa.inspect(engine)
    conn = engine.connect()

    # 1. Verify 4 Seed Hubs exist
    hubs = conn.execute(sa.text("SELECT id, hub_type, slug, owner_id FROM hubs")).fetchall()
    assert len(hubs) == 4, f"Expected 4 seed hubs, found {len(hubs)}"
    hub_types = {h[1] for h in hubs}
    assert hub_types == {"ingestion", "agent", "workflow", "eval"}

    # 2. Verify 5 Seed Hub Links exist
    links = conn.execute(sa.text("SELECT source_hub_id, target_hub_id, access_level FROM hub_links")).fetchall()
    assert len(links) == 5, f"Expected 5 seed hub links, found {len(links)}"

    # 3. Verify Memberships: 3 active users * 4 hubs = 12 membership rows
    members = conn.execute(sa.text("SELECT user_id, hub_id, hub_role FROM hub_members")).fetchall()
    assert len(members) == 12, f"Expected 12 member rows, found {len(members)}"

    # Check mapped hub roles
    admin_mems = conn.execute(
        sa.text("SELECT hub_role FROM hub_members WHERE user_id = (SELECT id FROM users WHERE email = 'admin@contained.local')")
    ).fetchall()
    assert all(m[0] == "owner" for m in admin_mems), "Admin user must be enrolled with 'owner' role"

    editor_mems = conn.execute(
        sa.text("SELECT hub_role FROM hub_members WHERE user_id = (SELECT id FROM users WHERE email = 'editor@contained.local')")
    ).fetchall()
    assert all(m[0] == "contributor" for m in editor_mems), "Editor user must be enrolled with 'contributor' role"

    # 4. Verify hub_id Backfill & NOT NULL on domain tables
    cols = {c["name"]: c for c in inspector.get_columns("syntraflow_collections")}
    assert cols["hub_id"]["nullable"] is False

    cols = {c["name"]: c for c in inspector.get_columns("agent_definitions")}
    assert cols["hub_id"]["nullable"] is False

    cols = {c["name"]: c for c in inspector.get_columns("workflows")}
    assert cols["hub_id"]["nullable"] is False

    cols = {c["name"]: c for c in inspector.get_columns("eval_test_suites")}
    assert cols["hub_id"]["nullable"] is False

    # Check backfilled values are non-null
    null_collections = conn.execute(sa.text("SELECT count(*) FROM syntraflow_collections WHERE hub_id IS NULL")).scalar()
    assert null_collections == 0

    null_agents = conn.execute(sa.text("SELECT count(*) FROM agent_definitions WHERE hub_id IS NULL")).scalar()
    assert null_agents == 0

    # 5. Verify physical_name populated and tenant_id / users.role dropped
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    assert "role" not in user_cols
    assert "platform_role" in user_cols

    col_cols = {c["name"] for c in inspector.get_columns("syntraflow_collections")}
    assert "tenant_id" not in col_cols
    assert "physical_name" in col_cols

    physical_names = conn.execute(sa.text("SELECT physical_name FROM syntraflow_collections")).fetchall()
    p_names = {p[0] for p in physical_names}
    assert "default__collection_alpha" in p_names
    assert "default__collection_beta" in p_names

    # 6. Test Idempotency: Upgrade head again should be a no-op
    command.upgrade(config, "b7c2d3e4f5a6")
    hubs_after = conn.execute(sa.text("SELECT count(*) FROM hubs")).scalar()
    assert hubs_after == 4

    links_after = conn.execute(sa.text("SELECT count(*) FROM hub_links")).scalar()
    assert links_after == 5

    mems_after = conn.execute(sa.text("SELECT count(*) FROM hub_members")).scalar()
    assert mems_after == 12

    # 7. Test Round-trip Downgrade to Stage 1 and Upgrade back to Stage 2
    conn.close()
    command.downgrade(config, "a6b1c2d3e4f5")

    inspector = sa.inspect(engine)
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    assert "role" in user_cols

    col_cols = {c["name"] for c in inspector.get_columns("syntraflow_collections")}
    assert "tenant_id" in col_cols

    # Upgrade back to Stage 2
    command.upgrade(config, "b7c2d3e4f5a6")

    conn = engine.connect()
    hubs_roundtrip = conn.execute(sa.text("SELECT count(*) FROM hubs")).scalar()
    assert hubs_roundtrip == 4

    conn.close()
    engine.dispose()