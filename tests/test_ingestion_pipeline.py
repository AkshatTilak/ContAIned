from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.models.database import Base, Hub, User
from projects.syntraflow.src.database.models import (
    SyntraFlowCollection,
    SyntraFlowDocument,
    SyntraFlowChunk,
    SyntraFlowJob,
)
from projects.syntraflow.src.ingestion.pipeline import (
    assert_collection_in_hub,
    ingest_document_pipeline,
)


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


@pytest.fixture(autouse=True)
def patch_ocr_and_neo4j():
    """Patch extract_layout_ocr and write_to_neo4j for pipeline unit tests."""
    with patch(
        "projects.syntraflow.src.ingestion.pipeline.extract_layout_ocr",
        new=AsyncMock(return_value={"text": "Sample policy document content."}),
    ), patch(
        "projects.syntraflow.src.ingestion.pipeline.write_to_neo4j",
        new=AsyncMock(return_value=None),
    ):
        yield


@pytest_asyncio.fixture
async def sample_setup(db_session: AsyncSession):
    """Seed test user, hub, and collection."""
    user = User(
        id="usr-owner-1",
        email="owner@example.com",
        display_name="Owner User",
        platform_role="admin",
        status="active",
    )
    hub = Hub(
        id="hub-ingest-01",
        slug="ingest_test",
        name="Ingestion Hub 1",
        hub_type="ingestion",
        owner_id=user.id,
    )
    col = SyntraFlowCollection(
        id="col-01",
        hub_id=hub.id,
        name="policies",
        physical_name="ingest_test__policies",
        vector_dimension=1024,
    )
    db_session.add_all([user, hub, col])
    await db_session.commit()
    return {"user": user, "hub": hub, "collection": col}


@pytest.mark.asyncio
async def test_assert_collection_in_hub(db_session: AsyncSession, sample_setup):
    """Test assert_collection_in_hub validation."""
    hub = sample_setup["hub"]
    col = sample_setup["collection"]

    # Valid check
    found = await assert_collection_in_hub(db_session, hub_id=hub.id, collection_id=col.id)
    assert found.id == col.id

    # Non-existent collection
    with pytest.raises(HTTPException) as exc_1:
        await assert_collection_in_hub(db_session, hub_id=hub.id, collection_id="non-existent-col")
    assert exc_1.value.status_code == 404

    # Wrong hub_id -> 404 Not Found (not 403)
    with pytest.raises(HTTPException) as exc_2:
        await assert_collection_in_hub(db_session, hub_id="wrong-hub-id", collection_id=col.id)
    assert exc_2.value.status_code == 404


@pytest.mark.asyncio
async def test_ingest_document_pipeline_stamping_and_scoping(db_session: AsyncSession, sample_setup):
    """Test ingest_document_pipeline stamps hub_id & collection_id onto document, chunks, and vector payloads."""
    hub = sample_setup["hub"]
    col = sample_setup["collection"]

    mock_inference = MagicMock()
    mock_inference.embed = AsyncMock(return_value=[[0.1] * 1024])
    mock_inference.ocr = AsyncMock(return_value={"text": "Sample policy document content."})

    doc_id = await ingest_document_pipeline(
        file_bytes=b"Sample policy document content.",
        filename="policy.pdf",
        db=db_session,
        inference_client=mock_inference,
        hub_id=hub.id,
        collection_id=col.id,
    )

    assert doc_id is not None

    # Verify SyntraFlowDocument persisted with hub_id and collection_id
    stmt = select(SyntraFlowDocument).where(SyntraFlowDocument.id == doc_id)
    res = await db_session.execute(stmt)
    doc = res.scalar_one()
    assert doc.hub_id == hub.id
    assert doc.collection_id == col.id
    assert doc.filename == "policy.pdf"

    # Verify SyntraFlowChunk inherits hub_id
    chunk_stmt = select(SyntraFlowChunk).where(SyntraFlowChunk.document_id == doc.id)
    chunk_res = await db_session.execute(chunk_stmt)
    chunks = list(chunk_res.scalars().all())
    assert len(chunks) > 0
    for ch in chunks:
        assert ch.hub_id == hub.id


@pytest.mark.asyncio
async def test_embedding_dimension_mismatch(db_session: AsyncSession, sample_setup):
    """Test that embedding dimension mismatch raises HTTP 409."""
    hub = sample_setup["hub"]
    col = sample_setup["collection"]

    # Mock inference client returning 512 dimensions when collection expects 1024
    mock_inference = MagicMock()
    mock_inference.embed = AsyncMock(return_value=[[0.1] * 512])

    with pytest.raises(HTTPException) as exc:
        await ingest_document_pipeline(
            file_bytes=b"Content for dimension test.",
            filename="dim_test.txt",
            db=db_session,
            inference_client=mock_inference,
            hub_id=hub.id,
            collection_id=col.id,
        )

    assert exc.value.status_code == 409
    assert "Embedding dimension mismatch" in exc.value.detail
