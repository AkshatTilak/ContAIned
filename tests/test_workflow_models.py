"""Unit tests for S6-06a: Workflow, Version & Run Models, Schemas, and Fixtures."""

import uuid
from datetime import datetime
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from common.models.database import (
    Base,
    Hub,
    User,
    WorkflowDefinition,
    WorkflowVersion,
    WorkflowRun,
    EvalFlowTrace,
)
from common.models.hub_enums import (
    WORKFLOW_STATUSES,
    WORKFLOW_RUN_STATUSES,
    WORKFLOW_RUN_TRIGGERS,
)
from common.schemas.workflows import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowSummary,
    WorkflowDetail,
    WorkflowVersionSummary,
    WorkflowVersionDetail,
    WorkflowRunSummary,
    WorkflowRunDetail,
    WorkflowGraph,
)
from tests.fixtures.workflows import make_workflow, make_version, make_run


@pytest_asyncio.fixture
async def db_session():
    """Create in-memory SQLite database session fixture."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_workflow_models_crud(db_session: AsyncSession):
    """Verify CRUD operations on WorkflowDefinition, WorkflowVersion, and WorkflowRun."""
    # 1. Create User and Hub
    user_id = str(uuid.uuid4())
    user = User(id=user_id, email="wf_test@example.com", display_name="WF Tester", platform_role="admin", status="active")
    db_session.add(user)

    hub_id = str(uuid.uuid4())
    hub = Hub(id=hub_id, name="Workflow Hub Test", slug="wf-test-hub", hub_type="workflow", owner_id=user_id)
    db_session.add(hub)
    await db_session.commit()

    # 2. Create WorkflowDefinition
    wf = make_workflow(hub_id=hub_id, name="Customer Onboarding", slug="customer-onboarding", created_by=user_id)
    db_session.add(wf)
    await db_session.commit()

    # 3. Create WorkflowVersion
    version = make_version(workflow_id=wf.id, version_number=1, created_by=user_id)
    db_session.add(version)
    await db_session.commit()

    # Link version back to workflow
    wf.draft_version_id = version.id
    wf.published_version_id = version.id
    wf.status = "published"
    await db_session.commit()

    # 4. Create WorkflowRun
    run = make_run(hub_id=hub_id, workflow_id=wf.id, version_id=version.id, trigger="manual", started_by=user_id)
    db_session.add(run)
    await db_session.commit()

    # 5. Create EvalFlowTrace linked to run
    trace = EvalFlowTrace(
        id=str(uuid.uuid4()),
        hub_id=hub_id,
        run_id=run.id,
        workflow_id=wf.id,
        node_id="start-1",
        node_type="start",
        sequence=1,
        input_state={"query": "hello"},
        output_state={"status": "ok"},
        latency_ms=12.5,
    )
    db_session.add(trace)
    await db_session.commit()

    # Query and assert
    stmt = select(WorkflowDefinition).where(WorkflowDefinition.id == wf.id)
    res = (await db_session.execute(stmt)).scalar_one()
    assert res.name == "Customer Onboarding"
    assert res.slug == "customer-onboarding"
    assert res.status == "published"
    assert res.published_version_id == version.id

    stmt_run = select(WorkflowRun).where(WorkflowRun.id == run.id)
    run_res = (await db_session.execute(stmt_run)).scalar_one()
    assert run_res.status == "succeeded"
    assert run_res.trigger == "manual"
    assert run_res.hub_id == hub_id

    stmt_trace = select(EvalFlowTrace).where(EvalFlowTrace.run_id == run.id)
    trace_res = (await db_session.execute(stmt_trace)).scalar_one()
    assert trace_res.sequence == 1
    assert trace_res.node_id == "start-1"


def test_workflow_schemas():
    """Verify Pydantic schemas validation for workflow components."""
    graph = WorkflowGraph(
        nodes=[{"id": "n1", "type": "agent"}],
        edges=[],
        viewport={"x": 0, "y": 0, "zoom": 1},
    )
    create_dto = WorkflowCreate(
        name="Automation Flow",
        slug="automation-flow",
        description="Automated tasks",
        tags_json=["automation", "v6"],
        graph=graph,
    )
    assert create_dto.name == "Automation Flow"

    update_dto = WorkflowUpdate(status="published")
    assert update_dto.status == "published"

    with pytest.raises(ValueError, match="Invalid workflow status"):
        WorkflowUpdate(status="invalid_status")

    run_summary = WorkflowRunSummary(
        id=str(uuid.uuid4()),
        hub_id=str(uuid.uuid4()),
        workflow_id=str(uuid.uuid4()),
        trigger="api",
        status="succeeded",
        started_at=datetime.utcnow(),
    )
    assert run_summary.trigger == "api"

    with pytest.raises(ValueError, match="Invalid run trigger"):
        WorkflowRunSummary(
            id=str(uuid.uuid4()),
            hub_id=str(uuid.uuid4()),
            workflow_id=str(uuid.uuid4()),
            trigger="unsupported_trigger",
            status="succeeded",
            started_at=datetime.utcnow(),
        )
