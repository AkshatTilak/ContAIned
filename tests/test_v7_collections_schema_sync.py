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


def test_collections_schema_sync_migration(temp_db_config):
    config, db_url, _ = temp_db_config

    engine = sa.create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE datastore_bindings (
                id VARCHAR(36) PRIMARY KEY
            );
        """))
        conn.execute(sa.text("""
            CREATE TABLE api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT
            );
        """))
        conn.execute(sa.text("""
            CREATE TABLE syntraflow_collections (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                physical_name VARCHAR(320) NOT NULL,
                embedding_model VARCHAR(255) NOT NULL,
                vector_dimension FLOAT NOT NULL,
                description TEXT,
                created_at DATETIME,
                hub_id VARCHAR(36) NOT NULL
            );
        """))
        conn.execute(sa.text("""
            CREATE TABLE syntraflow_documents (
                id VARCHAR(36) PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME,
                hub_id VARCHAR(36) NOT NULL
            );
        """))
        conn.execute(sa.text("""
            CREATE TABLE syntraflow_jobs (
                id VARCHAR(36) PRIMARY KEY,
                status VARCHAR(20) NOT NULL,
                created_at DATETIME,
                hub_id VARCHAR(36) NOT NULL
            );
        """))

    # Stamp existing DB state as i9c0d1e2f3a4
    command.stamp(config, "i9c0d1e2f3a4")

    # Upgrade to head revision: j1e2f3a4b5c6
    command.upgrade(config, "j1e2f3a4b5c6")

    inspector = sa.inspect(engine)

    # 1. Assert syntraflow_collections table has retrieval_config_json and datastore_binding_id columns
    cols = {c["name"]: c for c in inspector.get_columns("syntraflow_collections")}
    assert "retrieval_config_json" in cols, "'retrieval_config_json' column missing from syntraflow_collections"
    assert "datastore_binding_id" in cols, "'datastore_binding_id' column missing from syntraflow_collections"

    # 2. Assert syntraflow_documents and syntraflow_jobs have collection_id
    doc_cols = {c["name"] for c in inspector.get_columns("syntraflow_documents")}
    assert "collection_id" in doc_cols, "'collection_id' column missing from syntraflow_documents"

    job_cols = {c["name"] for c in inspector.get_columns("syntraflow_jobs")}
    assert "collection_id" in job_cols, "'collection_id' column missing from syntraflow_jobs"

    # 3. Assert api_key_usage table exists
    assert "api_key_usage" in inspector.get_table_names()

    # 4. Downgrade to i9c0d1e2f3a4
    command.downgrade(config, "i9c0d1e2f3a4")
    inspector = sa.inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("syntraflow_collections")}
    assert "retrieval_config_json" not in cols, "'retrieval_config_json' should be dropped after downgrade"
    assert "datastore_binding_id" not in cols, "'datastore_binding_id' should be dropped after downgrade"
    assert "api_key_usage" not in inspector.get_table_names()

    engine.dispose()
