
import pytest
pytestmark = pytest.mark.unit
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


@pytest.mark.asyncio
async def test_collection_and_job_pipeline_config(db: AsyncSession):
    from projects.syntraflow.src.database.models import SyntraFlowCollection, SyntraFlowJob
    hub_id = str(uuid.uuid4())
    col_id = str(uuid.uuid4())

    pipeline_cfg = {
        "ocr_engine": "direct",
        "chunking_strategy": "recursive",
        "chunk_size": 1024,
        "chunk_overlap": 128,
        "embedding_model": "harrier-0.6b",
        "summary_model": "gemini/gemini-2.5-flash",
        "graph_model": "gemini/gemini-2.5-flash",
        "post_processors": ["summary_gen", "kg_extract"]
    }

    col = SyntraFlowCollection(
        id=col_id,
        hub_id=hub_id,
        name="test_col",
        physical_name=f"{hub_id}__test_col",
        embedding_model="harrier-0.6b",
        vector_dimension=1024,
        pipeline_config_json=pipeline_cfg,
    )
    db.add(col)
    await db.commit()

    job = SyntraFlowJob(
        id=uuid.uuid4(),
        hub_id=hub_id,
        collection_id=col_id,
        status="queued",
        pipeline_config_json=pipeline_cfg,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    assert job.pipeline_config_json["ocr_engine"] == "direct"
    assert job.pipeline_config_json["embedding_model"] == "harrier-0.6b"
    assert "kg_extract" in job.pipeline_config_json["post_processors"]

