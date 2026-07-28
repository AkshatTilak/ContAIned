import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from common.models.database import Base, Hub, User, DatastoreBinding, AuditLog
from common.models.hub_enums import (
    HUB_TYPE_INGESTION,
    STORE_TYPES,
    HEALTH_STATUSES,
    platform_default_binding,
)
from common.security.crypto import (
    encrypt_secret,
    decrypt_secret,
    mask_connection_uri,
    SecretDecryptionError,
)


@pytest.fixture
def db_session():
    """In-memory SQLite database session fixture."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_encryption_roundtrip():
    """Test encrypt_secret and decrypt_secret roundtrip and edge cases."""
    assert encrypt_secret(None) is None
    assert encrypt_secret("") is None

    plain = "my_super_secret_db_password"
    cipher1 = encrypt_secret(plain)
    cipher2 = encrypt_secret(plain)

    assert cipher1 != plain
    assert cipher1 != cipher2  # Non-deterministic IV
    assert decrypt_secret(cipher1) == plain
    assert decrypt_secret(cipher2) == plain

    assert decrypt_secret(None) is None
    assert decrypt_secret("") is None


def test_decryption_failure():
    """Test decrypt_secret raises SecretDecryptionError on invalid payload."""
    with pytest.raises(SecretDecryptionError):
        decrypt_secret("invalid-ciphertext-payload")


def test_mask_connection_uri():
    """Test mask_connection_uri for various schemes, credentials, and query params."""
    assert mask_connection_uri("postgresql://app:s3cret@db:5432/contained") == "postgresql://app:***@db:5432/contained"
    assert mask_connection_uri("http://qdrant:6333") == "http://qdrant:6333"
    assert mask_connection_uri("bolt://neo4j:pw@graph:7687") == "bolt://neo4j:***@graph:7687"
    
    # Query string masking
    uri_param = "http://store:9200?user=app&password=hunter2&token=abc123 secret"
    masked = mask_connection_uri(uri_param)
    assert "hunter2" not in masked
    assert "abc123 secret" not in masked
    assert "password=***" in masked

    # Malformed URI fail-closed
    assert mask_connection_uri(None) == "***"
    assert mask_connection_uri("") == "***"


def test_platform_default_binding_helper():
    """Test platform_default_binding for all store types."""
    for st in STORE_TYPES:
        binding = platform_default_binding(st)
        assert binding["id"] is None
        assert binding["is_default"] is True
        assert binding["store_type"] == st
        assert "***" not in binding["connection_uri"] or "contained" in binding["connection_uri"]

    with pytest.raises(ValueError, match="Invalid store_type"):
        platform_default_binding("redis")


def test_datastore_binding_constraints(db_session):
    """Test DatastoreBinding unique constraints and validations."""
    user = User(email="owner@example.com", provider="local", provider_id="p1", display_name="Owner")
    db_session.add(user)
    db_session.commit()

    hub = Hub(slug="ingest", name="Ingestion Hub", hub_type=HUB_TYPE_INGESTION, owner_id=user.id)
    db_session.add(hub)
    db_session.commit()

    b1 = DatastoreBinding(hub_id=hub.id, name="Primary Vector", store_type="qdrant", connection_uri="http://qdrant:6333")
    db_session.add(b1)
    db_session.commit()

    # Duplicate (hub_id, name) should fail
    b_dup = DatastoreBinding(hub_id=hub.id, name="Primary Vector", store_type="neo4j", connection_uri="bolt://neo4j:7687")
    db_session.add(b_dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Invalid store_type
    with pytest.raises(ValueError, match="Invalid store_type"):
        DatastoreBinding(hub_id=hub.id, name="Bad Store", store_type="mongo", connection_uri="mongodb://localhost")

    # Invalid health_status
    with pytest.raises(ValueError, match="Invalid health_status"):
        DatastoreBinding(hub_id=hub.id, name="Bad Health", store_type="postgres", connection_uri="postgresql://db", health_status="broken")


def test_hub_deletion_audit_log_and_bindings(db_session):
    """Test deleting Hub cascades datastore_bindings but sets audit_log.hub_id to NULL."""
    user = User(email="actor@example.com", provider="local", provider_id="p2", display_name="Actor")
    db_session.add(user)
    db_session.commit()

    hub = Hub(slug="audited", name="Audited Hub", hub_type=HUB_TYPE_INGESTION, owner_id=user.id)
    db_session.add(hub)
    db_session.commit()

    binding = DatastoreBinding(hub_id=hub.id, name="Store 1", store_type="qdrant", connection_uri="http://qdrant:6333")
    audit = AuditLog(hub_id=hub.id, actor_user_id=user.id, action="create", resource_type="hub", resource_id=hub.id, summary="Created hub")
    db_session.add_all([binding, audit])
    db_session.commit()

    audit_id = audit.id
    assert db_session.query(DatastoreBinding).count() == 1
    assert db_session.query(AuditLog).count() == 1

    # Delete hub
    db_session.delete(hub)
    db_session.commit()

    # Bindings deleted, audit log preserved with hub_id IS NULL
    assert db_session.query(DatastoreBinding).count() == 0
    saved_audit = db_session.query(AuditLog).filter_by(id=audit_id).first()
    assert saved_audit is not None
    assert saved_audit.hub_id is None
    assert saved_audit.actor_user_id == user.id
