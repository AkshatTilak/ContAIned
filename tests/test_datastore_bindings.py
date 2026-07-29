"""Unit & Integration tests for Datastore Binding Manager & Client Resolution (S6-04b)."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.models.database import Base, Hub, User, AuditLog, DatastoreBinding
from projects.syntraflow.src.database.models import SyntraFlowCollection
from projects.syntraflow.src.datastores import (
    DatastoreBindingManager,
    DatastoreUnavailableError,
    decrypt_credentials,
    encrypt_credentials,
    invalidate_hub_clients,
    mask_uri,
    resolve_graph_client,
    resolve_relational_engine,
    resolve_vector_client,
)
from projects.syntraflow.src.datastores.schemas import DatastoreBindingResponse


@pytest.fixture
def memory_db():
    """In-memory SQLite async database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    return engine


@pytest_asyncio.fixture
async def db_session(memory_db):
    """Async database session fixture."""
    async with memory_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(memory_db, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with memory_db.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def sample_hub(db_session: AsyncSession) -> Hub:
    """Create a sample ingestion hub for testing."""
    user = User(
        id="user-owner-1",
        email="owner@example.com",
        display_name="Owner User",
        platform_role="admin",
        status="active",
    )
    hub = Hub(
        id="hub-test-ingestion-01",
        slug="ingest-test",
        name="Ingestion Test Hub",
        hub_type="ingestion",
        owner_id="user-owner-1",
    )
    db_session.add(user)
    db_session.add(hub)
    await db_session.commit()
    return hub


@pytest.mark.asyncio
async def test_crypto_and_masking():
    """Test Fernet encryption, decryption, and URI password masking."""
    payload = {"username": "admin", "password": "super_secret_password_123"}
    enc = encrypt_credentials(payload)
    assert enc is not None
    assert "super_secret_password_123" not in enc

    dec = decrypt_credentials(enc)
    assert dec == payload

    assert decrypt_credentials(None) == {}

    uri = "postgresql://myuser:mysecretpass@localhost:5432/mydb"
    masked = mask_uri(uri)
    assert masked == "postgresql://myuser:***@localhost:5432/mydb"
    assert "mysecretpass" not in masked


@pytest.mark.asyncio
async def test_datastore_binding_crud_and_single_default(db_session: AsyncSession, sample_hub: Hub):
    """Test DatastoreBindingManager CRUD, uniqueness, and single default constraint."""
    mgr = DatastoreBindingManager(db_session)

    # 1. Create first Qdrant binding as default
    b1 = await mgr.create_binding(
        hub_id=sample_hub.id,
        name="Qdrant Primary",
        store_type="qdrant",
        connection_uri="http://qdrant-primary:6333",
        credentials={"api_key": "key-123"},
        is_default=True,
    )
    assert b1.id is not None
    assert b1.is_default is True

    # Check AuditLog row created
    audit_res = await db_session.execute(select(AuditLog).where(AuditLog.resource_id == b1.id))
    audit = audit_res.scalar_one()
    assert audit.action == "create"
    assert audit.resource_type == "datastore_binding"
    assert "key-123" not in str(audit.after_json)

    # 2. Create second Qdrant binding set to default -> b1.is_default should become False
    b2 = await mgr.create_binding(
        hub_id=sample_hub.id,
        name="Qdrant Secondary",
        store_type="qdrant",
        connection_uri="http://qdrant-secondary:6333",
        credentials={"api_key": "key-456"},
        is_default=True,
    )

    await db_session.refresh(b1)
    assert b2.is_default is True
    assert b1.is_default is False

    # 3. Duplicate name check
    with pytest.raises(ValueError, match="already exists in this hub"):
        await mgr.create_binding(
            hub_id=sample_hub.id,
            name="Qdrant Primary",
            store_type="qdrant",
            connection_uri="http://qdrant-dup:6333",
        )

    # 4. List bindings (should list custom b1, b2, and synthetic defaults for neo4j, postgres, opensearch)
    bindings = await mgr.list_bindings(hub_id=sample_hub.id)
    store_types = [b["store_type"] for b in bindings]
    assert "qdrant" in store_types
    assert "neo4j" in store_types
    assert "postgres" in store_types
    assert "opensearch" in store_types

    # Find synthetic neo4j
    neo_synth = next(b for b in bindings if b["store_type"] == "neo4j" and b["is_synthetic"])
    assert neo_synth["id"] == "platform-default:neo4j"
    assert neo_synth["is_default"] is True

    # 5. Read DatastoreBindingResponse model serialization - ensure credentials never appear
    resp_obj = DatastoreBindingResponse.model_validate(b1)
    dumped = resp_obj.model_dump()
    assert "credentials" not in dumped
    assert "credentials_encrypted" not in dumped


@pytest.mark.asyncio
async def test_update_and_delete_protection(db_session: AsyncSession, sample_hub: Hub):
    """Test update, platform-default read-only guard, and collection deletion safety."""
    mgr = DatastoreBindingManager(db_session)

    b = await mgr.create_binding(
        hub_id=sample_hub.id,
        name="Postgres Main",
        store_type="postgres",
        connection_uri="postgresql://user:pass@localhost:5432/maindb",
    )

    # Cannot edit platform default
    with pytest.raises(ValueError, match="read-only"):
        await mgr.update_binding(hub_id=sample_hub.id, binding_id="platform-default:postgres", name="New Name")

    with pytest.raises(ValueError, match="read-only"):
        await mgr.delete_binding(hub_id=sample_hub.id, binding_id="platform-default:postgres")

    # Bind a collection to this datastore binding
    col = SyntraFlowCollection(
        id="col-01",
        hub_id=sample_hub.id,
        name="test_col",
        physical_name="ingest_test__test_col",
        datastore_binding_id=b.id,
    )
    db_session.add(col)
    await db_session.commit()

    # Attempting to delete in-use binding should fail with 409 error message
    with pytest.raises(ValueError, match="Binding is in use by collections"):
        await mgr.delete_binding(hub_id=sample_hub.id, binding_id=b.id)

    # Unbind collection
    col.datastore_binding_id = None
    await db_session.commit()

    # Now deletion succeeds
    await mgr.delete_binding(hub_id=sample_hub.id, binding_id=b.id)
    assert await mgr.get_binding(hub_id=sample_hub.id, binding_id=b.id) is None


@pytest.mark.asyncio
async def test_client_resolution_and_unreachable_guard(db_session: AsyncSession, sample_hub: Hub):
    """Test resolve_vector_client selection, caching, and unreachable error guard."""
    mgr = DatastoreBindingManager(db_session)

    # Create binding with health_status="unreachable"
    b = await mgr.create_binding(
        hub_id=sample_hub.id,
        name="Broken Qdrant",
        store_type="qdrant",
        connection_uri="http://broken-qdrant:6333",
        is_default=True,
    )
    b.health_status = "unreachable"
    await db_session.commit()

    # Resolving client for hub with unreachable default binding should raise DatastoreUnavailableError
    with pytest.raises(DatastoreUnavailableError) as exc_info:
        await resolve_vector_client(db_session, sample_hub.id)

    assert exc_info.value.hub_id == sample_hub.id
    assert exc_info.value.store_type == "qdrant"
    assert "Broken Qdrant" in str(exc_info.value)

    # Invalidate and fix health status
    invalidate_hub_clients(sample_hub.id)
    b.health_status = "healthy"
    await db_session.commit()

    # Now client resolves
    client = await resolve_vector_client(db_session, sample_hub.id)
    assert client is not None
