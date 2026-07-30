"""Unit tests for S6-06b: Version Lifecycle Service."""

import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.models.database import Base, Hub, User, WorkflowDefinition, WorkflowVersion
from projects.guardroute.src.workflows.version_service import (
    compute_etag,
    diff_versions,
    get_draft,
    update_draft,
    publish,
    restore,
    duplicate,
    list_versions,
    DraftConflict,
    ETagRequiredError,
    HubArchivedError,
)
from projects.guardroute.src.core.graph_parser import GraphValidationError
from tests.fixtures.workflows import make_workflow, make_version


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite database session fixture."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_compute_etag_stability():
    """Verify compute_etag returns stable hash for same graph content."""
    ver = make_version(workflow_id=str(uuid.uuid4()), version_number=1)
    etag1 = compute_etag(ver)
    etag2 = compute_etag(ver)
    assert etag1 == etag2
    assert etag1.startswith('W/"')

    ver.graph_json["nodes"].append({"id": "extra-node", "type": "action", "position": {"x": 0, "y": 0}, "data": {}})
    etag3 = compute_etag(ver)
    assert etag1 != etag3


def test_diff_versions_layout_agnostic():
    """Verify diff_versions detects node/edge edits while ignoring position/viewport changes."""
    base_graph = {
        "nodes": [
            {"id": "n1", "type": "start", "position": {"x": 0, "y": 0}, "data": {"label": "Start"}},
            {"id": "n2", "type": "end", "position": {"x": 100, "y": 100}, "data": {"label": "End"}},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }

    head_graph = {
        "nodes": [
            {"id": "n1", "type": "start", "position": {"x": 500, "y": 500}, "data": {"label": "Start Updated"}},
            {"id": "n3", "type": "action", "position": {"x": 200, "y": 200}, "data": {"label": "Action"}},
        ],
        "edges": [{"source": "n1", "target": "n3"}],
        "viewport": {"x": 10, "y": 20, "zoom": 2},
    }

    diff = diff_versions(base_graph, head_graph)
    assert diff.nodes_added == ["n3"]
    assert diff.nodes_removed == ["n2"]
    assert len(diff.nodes_changed) == 1
    assert diff.nodes_changed[0].node_id == "n1"
    assert "data" in diff.nodes_changed[0].changed_fields
    assert diff.edges_added == ["n1->n3"]
    assert diff.edges_removed == ["n1->n2"]


@pytest.mark.asyncio
async def test_get_draft_lazy_creation(db_session: AsyncSession):
    """Verify get_draft lazily creates a new draft version when draft_version_id is None."""
    user_id = str(uuid.uuid4())
    user = User(id=user_id, email="actor@example.com", display_name="Actor User", status="active")
    db_session.add(user)

    hub_id = str(uuid.uuid4())
    hub = Hub(id=hub_id, name="Test Hub", slug="test-hub", hub_type="workflow", owner_id=user_id)
    db_session.add(hub)
    await db_session.commit()

    wf = make_workflow(hub_id=hub_id, name="Pipeline Workflow", slug="pipeline-workflow", created_by=user_id)
    db_session.add(wf)
    await db_session.commit()

    draft = await get_draft(db_session, hub_id=hub_id, workflow_id=wf.id)
    assert draft is not None
    assert draft.version_number == 1
    assert wf.draft_version_id == draft.id


@pytest.mark.asyncio
async def test_update_draft_optimistic_locking(db_session: AsyncSession):
    """Verify update_draft succeeds with valid etag and raises DraftConflict on etag mismatch."""
    user_id = str(uuid.uuid4())
    user = User(id=user_id, email="lock@example.com", status="active")
    hub = Hub(id=str(uuid.uuid4()), name="Lock Hub", slug="lock-hub", hub_type="workflow", owner_id=user_id)
    db_session.add_all([user, hub])
    await db_session.commit()

    wf = make_workflow(hub_id=hub.id, name="Lock Workflow", slug="lock-wf", created_by=user_id)
    db_session.add(wf)
    await db_session.commit()

    draft = await get_draft(db_session, hub_id=hub.id, workflow_id=wf.id)
    etag = compute_etag(draft)

    valid_graph = {
        "nodes": [
            {"id": "start-1", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "end-1", "type": "final_message", "position": {"x": 200, "y": 0}, "data": {}},
        ],
        "edges": [{"source": "start-1", "target": "end-1"}],
    }

    res = await update_draft(
        db_session,
        hub_id=hub.id,
        workflow_id=wf.id,
        graph=valid_graph,
        expected_etag=etag,
        actor_id=user_id,
        change_note="Updated graph topology",
    )
    assert res.is_valid is True
    assert res.etag != etag

    # Attempt update with stale ETag -> DraftConflict
    with pytest.raises(DraftConflict) as exc_info:
        await update_draft(
            db_session,
            hub_id=hub.id,
            workflow_id=wf.id,
            graph=valid_graph,
            expected_etag=etag,  # stale etag
            actor_id=user_id,
        )
    assert "modified by another editor" in str(exc_info.value)


@pytest.mark.asyncio
async def test_publish_lifecycle(db_session: AsyncSession):
    """Verify publish freezes draft, sets published_version_id, and next get_draft creates v2."""
    user_id = str(uuid.uuid4())
    user = User(id=user_id, email="pub@example.com", status="active")
    hub = Hub(id=str(uuid.uuid4()), name="Pub Hub", slug="pub-hub", hub_type="workflow", owner_id=user_id)
    db_session.add_all([user, hub])
    await db_session.commit()

    wf = make_workflow(hub_id=hub.id, name="Publish Workflow", slug="pub-wf", created_by=user_id)
    db_session.add(wf)
    await db_session.commit()

    draft = await get_draft(db_session, hub_id=hub.id, workflow_id=wf.id)
    valid_graph = {
        "nodes": [
            {"id": "n1", "type": "start", "position": {"x": 0, "y": 0}},
            {"id": "n2", "type": "final_message", "position": {"x": 100, "y": 0}},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }
    await update_draft(db_session, hub_id=hub.id, workflow_id=wf.id, graph=valid_graph, expected_etag=None, actor_id=user_id)

    pub_ver = await publish(db_session, hub_id=hub.id, workflow_id=wf.id, actor_id=user_id, change_note="Initial Release")
    assert pub_ver.version_number == 1
    assert wf.published_version_id == pub_ver.id
    assert wf.draft_version_id is None
    assert wf.status == "published"

    # Next get_draft opens a fresh v2 draft
    v2_draft = await get_draft(db_session, hub_id=hub.id, workflow_id=wf.id)
    assert v2_draft.version_number == 2
    assert v2_draft.id != pub_ver.id
    assert wf.draft_version_id == v2_draft.id


@pytest.mark.asyncio
async def test_publish_invalid_graph_rejection(db_session: AsyncSession):
    """Verify publish raises GraphValidationError if graph topology is invalid."""
    user_id = str(uuid.uuid4())
    user = User(id=user_id, email="invalid@example.com", status="active")
    hub = Hub(id=str(uuid.uuid4()), name="Invalid Hub", slug="invalid-hub", hub_type="workflow", owner_id=user_id)
    db_session.add_all([user, hub])
    await db_session.commit()

    wf = make_workflow(hub_id=hub.id, name="Invalid Workflow", slug="invalid-wf", created_by=user_id)
    db_session.add(wf)
    await db_session.commit()

    invalid_graph = {
        "nodes": [
            {"id": "n1", "type": "start", "position": {"x": 0, "y": 0}},
            {"id": "n2", "type": "agent", "position": {"x": 100, "y": 0}},  # Non-terminal leaf
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }
    await update_draft(db_session, hub_id=hub.id, workflow_id=wf.id, graph=invalid_graph, expected_etag=None, actor_id=user_id)

    with pytest.raises(GraphValidationError):
        await publish(db_session, hub_id=hub.id, workflow_id=wf.id, actor_id=user_id)


@pytest.mark.asyncio
async def test_restore_version(db_session: AsyncSession):
    """Verify restore creates a new draft version copied from target historical version."""
    user_id = str(uuid.uuid4())
    user = User(id=user_id, email="restore@example.com", status="active")
    hub = Hub(id=str(uuid.uuid4()), name="Restore Hub", slug="restore-hub", hub_type="workflow", owner_id=user_id)
    db_session.add_all([user, hub])
    await db_session.commit()

    wf = make_workflow(hub_id=hub.id, name="Restore Workflow", slug="restore-wf", created_by=user_id)
    db_session.add(wf)
    await db_session.commit()

    # Create v1 and publish
    v1_graph = {
        "nodes": [
            {"id": "v1-start", "type": "start"},
            {"id": "v1-end", "type": "final_message"},
        ],
        "edges": [{"source": "v1-start", "target": "v1-end"}],
    }
    await update_draft(db_session, hub_id=hub.id, workflow_id=wf.id, graph=v1_graph, expected_etag=None, actor_id=user_id)
    await publish(db_session, hub_id=hub.id, workflow_id=wf.id, actor_id=user_id)

    # Now restore v1 into a new draft
    restored_draft = await restore(db_session, hub_id=hub.id, workflow_id=wf.id, version_number=1, actor_id=user_id)
    assert restored_draft.version_number == 2
    assert restored_draft.change_note == "Restored from v1"
    assert restored_draft.graph_json == v1_graph


@pytest.mark.asyncio
async def test_duplicate_workflow(db_session: AsyncSession):
    """Verify duplicate creates a new workflow definition with unique slug and cloned graph."""
    user_id = str(uuid.uuid4())
    user = User(id=user_id, email="dup@example.com", status="active")
    hub = Hub(id=str(uuid.uuid4()), name="Dup Hub", slug="dup-hub", hub_type="workflow", owner_id=user_id)
    db_session.add_all([user, hub])
    await db_session.commit()

    wf = make_workflow(hub_id=hub.id, name="Source Workflow", slug="source-wf", created_by=user_id)
    db_session.add(wf)
    await db_session.commit()

    graph = {
        "nodes": [{"id": "s", "type": "start"}, {"id": "e", "type": "final_message"}],
        "edges": [{"source": "s", "target": "e"}],
    }
    await update_draft(db_session, hub_id=hub.id, workflow_id=wf.id, graph=graph, expected_etag=None, actor_id=user_id)
    await publish(db_session, hub_id=hub.id, workflow_id=wf.id, actor_id=user_id)

    cloned_wf = await duplicate(db_session, hub_id=hub.id, workflow_id=wf.id, new_name="Source Workflow Copy", actor_id=user_id)
    assert cloned_wf.name == "Source Workflow Copy"
    assert cloned_wf.slug == "source-workflow-copy"
    assert cloned_wf.status == "draft"
    assert cloned_wf.draft_version_id is not None


@pytest.mark.asyncio
async def test_archived_hub_protection(db_session: AsyncSession):
    """Verify mutating operations raise HubArchivedError when hub is archived."""
    user_id = str(uuid.uuid4())
    user = User(id=user_id, email="archived@example.com", status="active")
    hub = Hub(id=str(uuid.uuid4()), name="Archived Hub", slug="arch-hub", hub_type="workflow", owner_id=user_id, is_archived=True)
    db_session.add_all([user, hub])
    await db_session.commit()

    wf = make_workflow(hub_id=hub.id, name="Archived Workflow", slug="arch-wf", created_by=user_id)
    db_session.add(wf)
    await db_session.commit()

    with pytest.raises(HubArchivedError):
        await update_draft(db_session, hub_id=hub.id, workflow_id=wf.id, graph={}, expected_etag=None, actor_id=user_id)

    with pytest.raises(HubArchivedError):
        await publish(db_session, hub_id=hub.id, workflow_id=wf.id, actor_id=user_id)

    with pytest.raises(HubArchivedError):
        await restore(db_session, hub_id=hub.id, workflow_id=wf.id, version_number=1, actor_id=user_id)
