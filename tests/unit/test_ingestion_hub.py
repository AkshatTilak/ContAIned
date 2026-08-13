
import pytest
pytestmark = pytest.mark.unit
"""Integration test suite for S6-04a Hub-Scoped Collection Manager."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
import pytest_asyncio
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.models.database import Base, Hub, User
from projects.syntraflow.src.collections.manager import CollectionManager, physical_collection_name
from projects.syntraflow.src.database.models import SyntraFlowDocument

# Setup in-memory test DB engine
test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
def mock_vector_client():
    """Return a VectorClient wrapper backed by an in-memory Qdrant client."""
    q_mem = QdrantClient(":memory:")
    wrapper = MagicMock()
    wrapper.get_client.return_value = q_mem
    return wrapper


@pytest.fixture(autouse=True)
def reset_db_state():
    """Reset DB schema before each test."""
    async def _reset():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset())


async def seed_hubs_and_user():
    """Seed test hubs and admin user into test DB."""
    async with TestingSessionLocal() as db:
        now = datetime.now(timezone.utc)

        u = User(
            id="user-owner-1",
            email="owner@example.com",
            platform_role="admin",
            status="active",
            created_at=now,
        )
        h1 = Hub(
            id="hub-ingest-1",
            name="Ingestion Hub Alpha",
            slug="ingest_alpha",
            hub_type="ingestion",
            owner_id="user-owner-1",
            created_at=now,
        )
        h2 = Hub(
            id="hub-ingest-2",
            name="Ingestion Hub Beta",
            slug="ingest_beta",
            hub_type="ingestion",
            owner_id="user-owner-1",
            created_at=now,
        )
        h_agent = Hub(
            id="hub-agent-1",
            name="Agent Hub Gamma",
            slug="agent_gamma",
            hub_type="agent",
            owner_id="user-owner-1",
            created_at=now,
        )
        db.add_all([u, h1, h2, h_agent])
        await db.commit()


def test_physical_collection_name_formatting():
    """Verify physical name generator cleans slugs and names."""
    res = physical_collection_name("Ingest Alpha!", "Company Policies")
    assert res == "ingest_alpha___company_policies"


@pytest.mark.asyncio
async def test_per_hub_collection_uniqueness_and_physical_isolation(mock_vector_client):
    """Test two distinct hubs can both own a collection named 'policies' with unique physical names."""
    await seed_hubs_and_user()

    async with TestingSessionLocal() as db:
        mgr = CollectionManager(db=db, vector_client=mock_vector_client)

        # Create 'policies' in Hub 1
        c1 = await mgr.create_collection(
            hub_id="hub-ingest-1",
            name="policies",
            description="Hub 1 Policies",
            retrieval_config={"strategy": "hybrid", "top_k": 10},
        )
        assert c1.hub_id == "hub-ingest-1"
        assert c1.name == "policies"
        assert c1.physical_name == "ingest_alpha__policies"
        assert c1.retrieval_config_json["strategy"] == "hybrid"

        # Create 'policies' in Hub 2
        c2 = await mgr.create_collection(
            hub_id="hub-ingest-2",
            name="policies",
            description="Hub 2 Policies",
            retrieval_config={"strategy": "dense", "top_k": 5},
        )
        assert c2.hub_id == "hub-ingest-2"
        assert c2.name == "policies"
        assert c2.physical_name == "ingest_beta__policies"
        assert c2.retrieval_config_json["strategy"] == "dense"


@pytest.mark.asyncio
async def test_idor_protection_wrong_hub_id(mock_vector_client):
    """Test get_collection returns None when queried with wrong hub_id."""
    await seed_hubs_and_user()

    async with TestingSessionLocal() as db:
        mgr = CollectionManager(db=db, vector_client=mock_vector_client)
        c1 = await mgr.create_collection(hub_id="hub-ingest-1", name="finance_docs")

        # Correct hub_id succeeds
        res_ok = await mgr.get_collection(hub_id="hub-ingest-1", collection_id=c1.id)
        assert res_ok is not None
        assert res_ok["name"] == "finance_docs"

        # Wrong hub_id returns None
        res_bad = await mgr.get_collection(hub_id="hub-ingest-2", collection_id=c1.id)
        assert res_bad is None


@pytest.mark.asyncio
async def test_invalid_collection_name_validation(mock_vector_client):
    """Test collection name containing '__' or invalid chars is rejected."""
    await seed_hubs_and_user()

    async with TestingSessionLocal() as db:
        mgr = CollectionManager(db=db, vector_client=mock_vector_client)
        with pytest.raises(ValueError, match="cannot contain '__'"):
            await mgr.create_collection(hub_id="hub-ingest-1", name="invalid__name")


@pytest.mark.asyncio
async def test_invalid_retrieval_strategy_validation(mock_vector_client):
    """Test invalid retrieval strategy raises error."""
    await seed_hubs_and_user()

    async with TestingSessionLocal() as db:
        mgr = CollectionManager(db=db, vector_client=mock_vector_client)
        with pytest.raises(Exception, match="Invalid retrieval strategy"):
            await mgr.create_collection(
                hub_id="hub-ingest-1",
                name="valid_name",
                retrieval_config={"strategy": "quantum_search"},
            )


@pytest.mark.asyncio
async def test_non_ingestion_hub_rejection(mock_vector_client):
    """Test attempting to manage collections in non-ingestion hub raises ValueError."""
    await seed_hubs_and_user()

    async with TestingSessionLocal() as db:
        mgr = CollectionManager(db=db, vector_client=mock_vector_client)
        with pytest.raises(ValueError, match="not 'ingestion'"):
            await mgr.create_collection(hub_id="hub-agent-1", name="test_col")


@pytest.mark.asyncio
async def test_delete_safety_non_empty_collection(mock_vector_client):
    """Test deleting collection with documents requires force=True."""
    await seed_hubs_and_user()

    async with TestingSessionLocal() as db:
        mgr = CollectionManager(db=db, vector_client=mock_vector_client)
        c1 = await mgr.create_collection(hub_id="hub-ingest-1", name="hr_files")

        # Seed document in Hub 1
        doc = SyntraFlowDocument(
            hub_id="hub-ingest-1",
            collection_id=c1.id,
            filename="handbook.pdf",
            content="Company handbook text...",
        )
        db.add(doc)
        await db.commit()

        # Delete without force -> ValueError 409
        with pytest.raises(ValueError, match="is not empty"):
            await mgr.delete_collection(hub_id="hub-ingest-1", collection_id=c1.id, force=False)

        # Delete with force=True -> succeeds
        res_del = await mgr.delete_collection(hub_id="hub-ingest-1", collection_id=c1.id, force=True)
        assert res_del["deleted"]["name"] == "hr_files"
        assert res_del["deleted"]["documents"] == 1


# --- API Route Integration Tests ---

from fastapi import FastAPI
from fastapi.testclient import TestClient
from common.clients.postgres import get_async_db
from gateway.api.ingestion_hub import router as ingestion_hub_router
from projects.syntraflow.src.datastores.crypto import encrypt_credentials, decrypt_credentials, mask_uri


@pytest_asyncio.fixture
async def api_client():
    """Create a FastAPI test client for testing ingestion hub routes."""
    app = FastAPI()
    app.include_router(ingestion_hub_router, prefix="/api")

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_test_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_async_db] = _get_test_db

    # Seed initial test data
    async with session_factory() as db:
        now = datetime.now(timezone.utc)
        admin = User(id="usr-admin", email="admin@example.com", platform_role="admin", status="active", created_at=now)
        viewer = User(id="usr-viewer", email="viewer@example.com", platform_role="member", status="active", created_at=now)
        hub_a = Hub(id="hub-support", name="Support Hub", slug="support", hub_type="ingestion", owner_id="usr-admin", created_at=now)
        hub_b = Hub(id="hub-eng", name="Eng Hub", slug="eng", hub_type="ingestion", owner_id="usr-admin", created_at=now)

        db.add_all([admin, viewer, hub_a, hub_b])
        await db.commit()

    return TestClient(app), session_factory


def test_datastore_credential_encryption_and_uri_masking():
    """Verify encryption of credentials at rest and URI masking on read."""
    payload = {"password": "supersecretpassword123!"}
    encrypted = encrypt_credentials(payload)
    assert "supersecretpassword123!" not in encrypted
    decrypted = decrypt_credentials(encrypted)
    assert decrypted["password"] == "supersecretpassword123!"

    masked = mask_uri("postgresql://user:secretpass@localhost:5432/mydb")
    assert "secretpass" not in masked
    assert "user:***@localhost" in masked

