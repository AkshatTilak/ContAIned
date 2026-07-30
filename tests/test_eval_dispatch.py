"""Unit & integration tests for polymorphic eval target resolution & runner dispatch (S6-07b)."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from common.models.database import (
    AgentDefinition,
    Base,
    EvalTestCase,
    EvalTestSuite,
    Hub,
    HubLink,
    HubMember,
    User,
    WorkflowDefinition,
)
from common.services import hub_resolver
from projects.evalops.src.runner import dispatch
from projects.evalops.src.runner.dispatch import ResolvedTarget, EvalCaseOutcome


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        u_owner = User(id="user-owner", email="owner@example.com", platform_role="member", status="active")
        session.add(u_owner)

        # Seed hubs: eval-1, agent-1, wf-1, agent-2
        eval_hub = Hub(id="eval-1", slug="eval-1", name="Eval Hub", hub_type="eval", owner_id="user-owner")
        agent_hub = Hub(id="agent-1", slug="agent-1", name="Agent Hub", hub_type="agent", owner_id="user-owner")
        unlinked_agent_hub = Hub(id="agent-2", slug="agent-2", name="Unlinked Agent Hub", hub_type="agent", owner_id="user-owner")
        wf_hub = Hub(id="wf-1", slug="wf-1", name="Workflow Hub", hub_type="workflow", owner_id="user-owner")
        session.add_all([eval_hub, agent_hub, unlinked_agent_hub, wf_hub])

        # Memberships
        for h_id in ["eval-1", "agent-1", "agent-2", "wf-1"]:
            session.add(HubMember(hub_id=h_id, user_id="user-owner", hub_role="owner"))

        # Target resources
        agent_res = AgentDefinition(
            id="agt-1",
            hub_id="agent-1",
            name="Target Agent",
            role="assistant",
            endpoint_slug="target-agent",
            system_prompt="Support agent",
            model_id="gpt-4o",
            is_active=True,
        )
        wf_res = WorkflowDefinition(
            id="wf-1",
            hub_id="wf-1",
            name="Target Workflow",
            slug="target-wf",
            status="published",
        )
        session.add_all([agent_res, wf_res])

        # Links: eval-1 -> agent-1 (read), eval-1 -> wf-1 (read)
        link_agent = HubLink(id="link-1", source_hub_id="eval-1", target_hub_id="agent-1", access_level="read")
        link_wf = HubLink(id="link-2", source_hub_id="eval-1", target_hub_id="wf-1", access_level="read")
        session.add_all([link_agent, link_wf])

        await session.commit()
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_resolve_target_agent_success(async_session: AsyncSession):
    session = async_session

    suite = EvalTestSuite(
        id="suite-1",
        hub_id="eval-1",
        name="Agent Suite",
        target_type="agent",
        target_hub_id="agent-1",
        target_id="agt-1",
    )
    session.add(suite)
    await session.commit()

    resolved = await dispatch.resolve_target(session, eval_hub_id="eval-1", suite=suite)
    assert isinstance(resolved, ResolvedTarget)
    assert resolved.target_type == "agent"
    assert resolved.hub_id == "agent-1"
    assert resolved.resource_id == "agt-1"
    assert resolved.name == "Target Agent"


@pytest.mark.asyncio
async def test_resolve_target_unlinked_hub_rejection(async_session: AsyncSession):
    session = async_session

    suite = EvalTestSuite(
        id="suite-unlinked",
        hub_id="eval-1",
        name="Unlinked Suite",
        target_type="agent",
        target_hub_id="agent-2",
        target_id="agt-2",
    )
    session.add(suite)
    await session.commit()

    with pytest.raises((ValueError, hub_resolver.HubLinkError)) as exc:
        await dispatch.resolve_target(session, eval_hub_id="eval-1", suite=suite)
    assert exc.value is not None


@pytest.mark.asyncio
async def test_resolve_target_cross_hub_mismatch(async_session: AsyncSession):
    session = async_session

    # agt-1 is in agent-1, but suite specifies target_hub_id="agent-2"
    suite = EvalTestSuite(
        id="suite-mismatch",
        hub_id="eval-1",
        name="Mismatch Suite",
        target_type="agent",
        target_hub_id="agent-2",
        target_id="agt-1",
    )
    session.add(suite)
    await session.commit()

    with pytest.raises((ValueError, hub_resolver.HubLinkError)) as exc:
        await dispatch.resolve_target(session, eval_hub_id="eval-1", suite=suite)
    assert exc.value is not None


@pytest.mark.asyncio
async def test_dispatch_run_agent_target(async_session: AsyncSession):
    session = async_session

    suite = EvalTestSuite(
        id="suite-run-1",
        hub_id="eval-1",
        name="Run Agent Suite",
        target_type="agent",
        target_hub_id="agent-1",
        target_id="agt-1",
    )
    case1 = EvalTestCase(id="case-1", suite_id="suite-run-1", input_query="What is AI?")
    case2 = EvalTestCase(id="case-2", suite_id="suite-run-1", input_query="Explain RAG.")
    session.add_all([suite, case1, case2])
    await session.commit()

    outcomes = await dispatch.dispatch_run(
        session,
        eval_hub_id="eval-1",
        suite=suite,
        cases=[case1, case2],
        run_id="run-test-1",
    )

    assert len(outcomes) == 2
    for o in outcomes:
        assert isinstance(o, EvalCaseOutcome)
        assert o.query in ["What is AI?", "Explain RAG."]
        assert o.actual_output is not None
