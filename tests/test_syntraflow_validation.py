"""Unit tests for Syntraflow Datastore Validation (sub_07_01)."""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from common.models.database import Base, Hub, DatastoreBinding
from projects.syntraflow.src.datastores.validator import (
    validate_datastore_binding,
    DatastoreValidationError,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_validate_datastore_binding_valid(db: AsyncSession):
    hub_id = str(uuid.uuid4())
    binding_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    binding = DatastoreBinding(
        id=binding_id,
        hub_id=hub_id,
        name="Test Qdrant",
        store_type="qdrant",
        connection_uri="http://localhost:6333",
        credentials_encrypted="enc",
        health_status="healthy",
        created_at=now,
        updated_at=now,
    )
    db.add(binding)
    await db.commit()

    res = await validate_datastore_binding(db, hub_id, binding_id, store_type="qdrant")
    assert res is not None
    assert res.id == binding_id


@pytest.mark.asyncio
async def test_validate_datastore_binding_unhealthy_raises(db: AsyncSession):
    hub_id = str(uuid.uuid4())
    binding_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    binding = DatastoreBinding(
        id=binding_id,
        hub_id=hub_id,
        name="Unhealthy Qdrant",
        store_type="qdrant",
        connection_uri="http://localhost:6333",
        credentials_encrypted="enc",
        health_status="unhealthy",
        created_at=now,
        updated_at=now,
    )
    db.add(binding)
    await db.commit()

    with pytest.raises(DatastoreValidationError, match="unhealthy"):
        await validate_datastore_binding(db, hub_id, binding_id, store_type="qdrant")


@pytest.mark.asyncio
async def test_validate_datastore_binding_not_found(db: AsyncSession):
    hub_id = str(uuid.uuid4())
    with pytest.raises(DatastoreValidationError, match="not found"):
        await validate_datastore_binding(db, hub_id, "nonexistent-id", store_type="qdrant")
