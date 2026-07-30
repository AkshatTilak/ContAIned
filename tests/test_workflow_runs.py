"""Unit tests for S6-06d: Run Orchestration, Persistence & SSE."""

import asyncio
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.models.database import (
    Base,
    Hub,
    User,
    AgentDefinition,
    HubLink,
    WorkflowDefinition,
    WorkflowVersion,
    WorkflowRun,
    EvalFlowTrace,
)
from projects.guardroute.src.workflows.run_service import (
    start_run,
    stream_run,
    cancel_run,
    get_run,
    list_runs,
    reconcile_orphaned_runs,
    redact_secrets,
    WorkflowNotFoundError,
    WorkflowNotPublishedError,
    RunNotFoundError,
    RunNotCancellableError,
)


@pytest_asyncio.fixture
async def db_setup():
    """In-memory SQLite database session and session factory fixture."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        user = User(id="user-runner-1", email="runner@example.com", display_name="Runner User")
        session.add(user)
        await session.commit()
        yield session, session_factory

    await engine.dispose()


@pytest.mark.asyncio
async def test_secret_redaction():
    """Test that redact_secrets strips keys matching secret pattern."""
    payload = {
        "user_query": "hello",
        "api_key": "secret_12345",
        "authorization": "Bearer token",
        "nested": {
            "password": "my_password",
            "normal": "value",
        },
        "items": [{"token": "abc"}, {"key": "ok"}],
    }
    redacted = redact_secrets(payload)
    assert redacted["user_query"] == "hello"
    assert redacted["api_key"] == "***"
    assert redacted["authorization"] == "***"
    assert redacted["nested"]["password"] == "***"
    assert redacted["nested"]["normal"] == "value"
    assert redacted["items"][0]["token"] == "***"
    assert redacted["items"][1]["key"] == "ok"


@pytest.mark.asyncio
async def test_published_run_execution(db_setup):
    """Test starting and completing a published workflow execution."""
    session, sf = db_setup

    hub = Hub(id="hub-wf-exec", name="Exec Hub", slug="exec-hub", hub_type="workflow", owner_id="user-runner-1")
    wf = WorkflowDefinition(
        id="wf-exec-1",
        hub_id="hub-wf-exec",
        name="Published Flow",
        slug="published-flow",
        status="published",
    )
    graph = {
        "nodes": [
            {"id": "n1", "type": "GatherNode", "data": {"label": "Gather"}},
            {"id": "n2", "type": "ActionNode", "data": {"action": "reply"}},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }
    ver = WorkflowVersion(
        id="ver-pub-1",
        workflow_id="wf-exec-1",
        version_number=1,
        graph_json=graph,
        is_valid=True,
    )
    wf.published_version_id = ver.id

    session.add_all([hub, wf, ver])
    await session.commit()

    from projects.guardroute.src.workflows.run_service import global_trace_collector
    if global_trace_collector._is_running:
        await global_trace_collector.stop()
    global_trace_collector.db_session_factory = sf
    await global_trace_collector.start()

    run = await start_run(
        session,
        hub_id="hub-wf-exec",
        workflow_id="wf-exec-1",
        input_json={"query": "test query", "api_key": "secret"},
        trigger="manual",
        started_by="user-runner-1",
        use_draft=False,
        session_factory=sf,
    )
    assert run.id is not None
    assert run.status == "queued"

    # Wait for execution task & trace collector queue processing to complete
    await asyncio.sleep(0.8)

    async with sf() as verify_session:
        run_db = (await verify_session.execute(
            select(WorkflowRun).where(WorkflowRun.id == run.id)
        )).scalar_one()
        assert run_db.status == "succeeded"
        assert run_db.duration_ms is not None
        assert run_db.finished_at is not None
        assert run_db.output_json.get("n1_output") is not None

        # Verify trace collection
        traces = (await verify_session.execute(
            select(EvalFlowTrace).where(EvalFlowTrace.run_id == run.id)
        )).scalars().all()
        assert len(traces) == 2


@pytest.mark.asyncio
async def test_dry_run_against_draft(db_setup):
    """Test dry run execution against draft graph."""
    session, sf = db_setup

    hub = Hub(id="hub-wf-draft", name="Draft Hub", slug="draft-hub", hub_type="workflow", owner_id="user-runner-1")
    wf = WorkflowDefinition(
        id="wf-draft-1",
        hub_id="hub-wf-draft",
        name="Draft Flow",
        slug="draft-flow",
        status="draft",
    )
    graph = {
        "nodes": [
            {"id": "node_draft", "type": "FinalMessageNode", "data": {"message": "hello"}},
        ],
        "edges": [],
    }
    draft_ver = WorkflowVersion(
        id="ver-draft-1",
        workflow_id="wf-draft-1",
        version_number=1,
        graph_json=graph,
        is_valid=True,
    )
    wf.draft_version_id = draft_ver.id

    session.add_all([hub, wf, draft_ver])
    await session.commit()

    run = await start_run(
        session,
        hub_id="hub-wf-draft",
        workflow_id="wf-draft-1",
        input_json={"test": True},
        use_draft=True,
        session_factory=sf,
    )
    assert run.input_json.get("_dry_run") is True
    assert run.version_id == draft_ver.id


@pytest.mark.asyncio
async def test_unpublished_workflow_rejection(db_setup):
    """Test that published run fails if workflow has no published version."""
    session, sf = db_setup

    hub = Hub(id="hub-wf-unpub", name="Unpub Hub", slug="unpub-hub", hub_type="workflow", owner_id="user-runner-1")
    wf = WorkflowDefinition(
        id="wf-unpub-1",
        hub_id="hub-wf-unpub",
        name="Unpublished Flow",
        slug="unpub-flow",
        status="draft",
    )
    session.add_all([hub, wf])
    await session.commit()

    with pytest.raises(WorkflowNotPublishedError):
        await start_run(
            session,
            hub_id="hub-wf-unpub",
            workflow_id="wf-unpub-1",
            input_json={},
            use_draft=False,
            session_factory=sf,
        )


@pytest.mark.asyncio
async def test_cancellation(db_setup):
    """Test cancelling a running workflow run."""
    session, sf = db_setup

    hub = Hub(id="hub-wf-cancel", name="Cancel Hub", slug="cancel-hub", hub_type="workflow", owner_id="user-runner-1")
    wf = WorkflowDefinition(
        id="wf-cancel-1",
        hub_id="hub-wf-cancel",
        name="Cancel Flow",
        slug="cancel-flow",
        status="published",
    )
    graph = {
        "nodes": [
            {"id": "n1", "type": "GatherNode", "data": {}},
            {"id": "n2", "type": "ActionNode", "data": {}},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }
    ver = WorkflowVersion(
        id="ver-cancel-1",
        workflow_id="wf-cancel-1",
        version_number=1,
        graph_json=graph,
        is_valid=True,
    )
    wf.published_version_id = ver.id

    session.add_all([hub, wf, ver])
    await session.commit()

    run = await start_run(
        session,
        hub_id="hub-wf-cancel",
        workflow_id="wf-cancel-1",
        input_json={},
        use_draft=False,
        session_factory=sf,
    )

    # Cancel immediately
    canceled = await cancel_run(
        session,
        hub_id="hub-wf-cancel",
        run_id=run.id,
        actor_id="user-runner-1",
    )
    assert canceled.status == "cancelled"

    # Cancelling terminal run again raises RunNotCancellableError
    with pytest.raises(RunNotCancellableError):
        await cancel_run(
            session,
            hub_id="hub-wf-cancel",
            run_id=run.id,
            actor_id="user-runner-1",
        )


@pytest.mark.asyncio
async def test_hub_scoping_enforcement(db_setup):
    """Test that get_run and list_runs enforce hub scoping and return 404 for cross-hub access."""
    session, sf = db_setup

    hub1 = Hub(id="hub-scope-1", name="Scope Hub 1", slug="scope-hub-1", hub_type="workflow", owner_id="user-runner-1")
    hub2 = Hub(id="hub-scope-2", name="Scope Hub 2", slug="scope-hub-2", hub_type="workflow", owner_id="user-runner-1")
    wf1 = WorkflowDefinition(id="wf-scope-1", hub_id="hub-scope-1", name="W1", slug="w1", status="published")
    ver1 = WorkflowVersion(id="ver-scope-1", workflow_id="wf-scope-1", version_number=1, graph_json={"nodes": [], "edges": []})
    wf1.published_version_id = ver1.id

    session.add_all([hub1, hub2, wf1, ver1])
    await session.commit()

    run = await start_run(
        session,
        hub_id="hub-scope-1",
        workflow_id="wf-scope-1",
        input_json={},
        use_draft=False,
        session_factory=sf,
    )

    # get_run with wrong hub_id raises RunNotFoundError
    with pytest.raises(RunNotFoundError):
        await get_run(session, hub_id="hub-scope-2", run_id=run.id)

    # list_runs with wrong hub_id returns empty list
    runs_h2 = await list_runs(session, hub_id="hub-scope-2", workflow_id="wf-scope-1")
    assert len(runs_h2) == 0


@pytest.mark.asyncio
async def test_reconcile_orphaned_runs(db_setup):
    """Test startup reconciliation hook marks orphaned queued/running runs as failed."""
    session, sf = db_setup

    hub = Hub(id="hub-orphan", name="Orphan Hub", slug="orphan-hub", hub_type="workflow", owner_id="user-runner-1")
    wf = WorkflowDefinition(id="wf-orphan", hub_id="hub-orphan", name="Orphan Flow", slug="orphan-flow", status="published")
    session.add_all([hub, wf])
    await session.flush()

    r1 = WorkflowRun(id="run-q1", hub_id="hub-orphan", workflow_id="wf-orphan", trigger="manual", status="queued")
    r2 = WorkflowRun(id="run-r1", hub_id="hub-orphan", workflow_id="wf-orphan", trigger="manual", status="running")
    r3 = WorkflowRun(id="run-s1", hub_id="hub-orphan", workflow_id="wf-orphan", trigger="manual", status="succeeded")
    session.add_all([r1, r2, r3])
    await session.commit()

    count = await reconcile_orphaned_runs(session)
    assert count == 2

    async with sf() as check_session:
        r1_db = (await check_session.execute(select(WorkflowRun).where(WorkflowRun.id == "run-q1"))).scalar_one()
        r2_db = (await check_session.execute(select(WorkflowRun).where(WorkflowRun.id == "run-r1"))).scalar_one()
        r3_db = (await check_session.execute(select(WorkflowRun).where(WorkflowRun.id == "run-s1"))).scalar_one()
        assert r1_db.status == "failed"
        assert r1_db.error_message == "ORPHANED_RUN"
        assert r2_db.status == "failed"
        assert r2_db.error_message == "ORPHANED_RUN"
        assert r3_db.status == "succeeded"
