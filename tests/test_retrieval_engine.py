"""Unit and integration tests for hub-scoped RetrievalEngine (S6-04d)."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.models.database import Base, Hub, User
from projects.syntraflow.src.database.models import SyntraFlowCollection
from projects.syntraflow.src.retrieval.engine import RetrievalEngine


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
async def seeded_hubs(db_session: AsyncSession):
    """Seed test user and two distinct hubs with collections."""
    user = User(
        id="usr-owner-1",
        email="owner@example.com",
        display_name="Owner User",
        platform_role="admin",
        status="active",
    )
    hub_a = Hub(
        id="hub-alpha",
        slug="alpha",
        name="Alpha Hub",
        hub_type="ingestion",
        owner_id=user.id,
    )
    hub_b = Hub(
        id="hub-beta",
        slug="beta",
        name="Beta Hub",
        hub_type="ingestion",
        owner_id=user.id,
    )
    col_a = SyntraFlowCollection(
        id="col-alpha-1",
        hub_id=hub_a.id,
        name="policies",
        physical_name="alpha__policies",
        vector_dimension=1024,
    )
    col_b = SyntraFlowCollection(
        id="col-beta-1",
        hub_id=hub_b.id,
        name="policies",
        physical_name="beta__policies",
        vector_dimension=1024,
    )
    db_session.add_all([user, hub_a, hub_b, col_a, col_b])
    await db_session.commit()
    return {"user": user, "hub_a": hub_a, "hub_b": hub_b, "col_a": col_a, "col_b": col_b}


@pytest.mark.asyncio
async def test_resolve_targets_hub_isolation(db_session: AsyncSession, seeded_hubs):
    """Test target collection resolution and cross-hub rejection."""
    hub_a = seeded_hubs["hub_a"]
    col_a = seeded_hubs["col_a"]
    col_b = seeded_hubs["col_b"]

    engine_a = RetrievalEngine(db_session, hub_a.id)

    # Resolving default (None) returns only Hub A's collections
    targets = await engine_a.resolve_targets(None)
    assert len(targets) == 1
    assert targets[0].id == col_a.id

    # Resolving valid collection in Hub A
    targets_explicit = await engine_a.resolve_targets([col_a.id])
    assert len(targets_explicit) == 1
    assert targets_explicit[0].id == col_a.id

    # Cross-hub rejection: requesting Hub B collection from Hub A engine raises 404 (never 403)
    with pytest.raises(HTTPException) as exc:
        await engine_a.resolve_targets([col_b.id])
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_hub_filter_construction(db_session: AsyncSession, seeded_hubs):
    """Test _hub_filter enforces hub_id and handles metadata filters."""
    hub_a = seeded_hubs["hub_a"]
    engine = RetrievalEngine(db_session, hub_a.id)

    qfilter = engine._hub_filter(collection_id="col-alpha-1", metadata_filter={"document_id": "doc-123"})
    must_keys = [c.key for c in qfilter.must]
    assert "hub_id" in must_keys
    assert "collection_id" in must_keys
    assert "document_id" in must_keys

    # Reject unsupported metadata keys with 422
    with pytest.raises(HTTPException) as exc:
        engine._hub_filter(metadata_filter={"unsupported_smuggled_key": "val"})
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_sparse_search_unindexed_rejection(db_session: AsyncSession, seeded_hubs):
    """Test sparse search on collection without sparse index raises 409."""
    hub_a = seeded_hubs["hub_a"]
    col_a = seeded_hubs["col_a"]
    engine = RetrievalEngine(db_session, hub_a.id)

    with pytest.raises(HTTPException) as exc:
        await engine.search_sparse(col_a, query="test query")
    assert exc.value.status_code == 409
    assert "Collection has no sparse index" in exc.value.detail


@pytest.mark.asyncio
async def test_hub_search_multi_collection(db_session: AsyncSession, seeded_hubs):
    """Test multi-collection search returns results tagged with hub_id, collection_id, and collection_name."""
    hub_a = seeded_hubs["hub_a"]
    col_a = seeded_hubs["col_a"]
    engine = RetrievalEngine(db_session, hub_a.id)

    mock_hit = MagicMock()
    mock_hit.id = "point-1"
    mock_hit.score = 0.95
    mock_hit.payload = {
        "text": "Alpha policy text content",
        "filename": "alpha.pdf",
        "document_id": "doc-alpha",
        "hub_id": hub_a.id,
        "collection_id": col_a.id,
    }

    mock_qdrant = MagicMock()
    mock_qdrant.search.return_value = [mock_hit]

    mock_vector_client = MagicMock()
    mock_vector_client.get_client.return_value = mock_qdrant

    with patch(
        "projects.syntraflow.src.retrieval.engine.resolve_vector_client",
        new=AsyncMock(return_value=mock_vector_client),
    ):
        results = await engine.search(query="policy", strategy="dense", limit=5)
        assert len(results) == 1
        res = results[0]
        assert res["hub_id"] == hub_a.id
        assert res["collection_id"] == col_a.id
        assert res["collection_name"] == "policies"
        assert res["text"] == "Alpha policy text content"
