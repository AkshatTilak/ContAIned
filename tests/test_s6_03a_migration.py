"""Migration verification test for S6-03a (Alembic upgrade/downgrade/upgrade idempotency)."""

import os
import tempfile
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect


@pytest.fixture
def scratch_db():
    """Create a temporary SQLite database file for testing migration lifecycle."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "scratch_test.db")
    db_url = f"sqlite+aiosqlite:///{db_path}"
    sync_db_url = f"sqlite:///{db_path}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    yield {
        "db_path": db_path,
        "sync_url": sync_db_url,
        "config": alembic_cfg,
    }

    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass


def test_s6_03a_migration_lifecycle(scratch_db):
    """Run upgrade head -> downgrade -1 -> upgrade head and verify table schema."""
    cfg = scratch_db["config"]
    sync_url = scratch_db["sync_url"]

    # 1. Run upgrade head
    command.upgrade(cfg, "head")

    engine = create_engine(sync_url)
    inspector = inspect(engine)

    # Check new tables exist
    tables = inspector.get_table_names()
    assert "users" in tables
    assert "user_identities" in tables
    assert "user_invites" in tables
    assert "password_reset_tokens" in tables

    # Check user columns after upgrade
    user_cols = [c["name"] for c in inspector.get_columns("users")]
    assert "platform_role" in user_cols
    assert "status" in user_cols
    assert "password_hash" in user_cols
    assert "role" not in user_cols
    assert "is_active" not in user_cols
    assert "provider" not in user_cols
    assert "provider_id" not in user_cols

    # 2. Run downgrade back to b7c2d3e4f5a6 (prior to v6_user_identity_invites)
    command.downgrade(cfg, "b7c2d3e4f5a6")

    inspector_down = inspect(engine)
    user_cols_down = [c["name"] for c in inspector_down.get_columns("users")]
    assert "role" in user_cols_down
    assert "is_active" in user_cols_down
    assert "provider" in user_cols_down
    assert "provider_id" in user_cols_down

    # 3. Run upgrade head again (idempotency check)
    command.upgrade(cfg, "head")

    inspector_up2 = inspect(engine)
    user_cols_up2 = [c["name"] for c in inspector_up2.get_columns("users")]
    assert "platform_role" in user_cols_up2
    assert "status" in user_cols_up2
    assert "role" not in user_cols_up2
    assert "is_active" not in user_cols_up2

    engine.dispose()
