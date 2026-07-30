"""Unit & integration tests for hub-scoped dataset & suite management (S6-07d)."""

import json
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from common.models.database import (
    AgentDefinition,
    Base,
    EvalRunHistory,
    EvalTestCase,
    EvalTestSuite,
    Hub,
    HubLink,
    HubMember,
    User,
    WorkflowDefinition,
)
from common.schemas.evalops import EvalTarget
from projects.evalops.src.datasets import manager
from projects.evalops.src.generation import synthetic


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        u_owner = User(id="user-owner", email="owner@example.com", platform_role="member", status="active")
        session.add(u_owner)

        eval_hub = Hub(id="eval-hub-1", slug="eval-1", name="Eval Hub", hub_type="eval", owner_id="user-owner")
        agent_hub = Hub(id="agent-hub-1", slug="agent-1", name="Agent Hub", hub_type="agent", owner_id="user-owner")
        wf_hub = Hub(id="wf-hub-1", slug="wf-1", name="Workflow Hub", hub_type="workflow", owner_id="user-owner")
        session.add_all([eval_hub, agent_hub, wf_hub])

        for h_id in ["eval-hub-1", "agent-hub-1", "wf-hub-1"]:
            session.add(HubMember(hub_id=h_id, user_id="user-owner", hub_role="owner"))

        agent_res = AgentDefinition(
            id="agt-100",
            hub_id="agent-hub-1",
            name="Target Agent",
            role="assistant",
            endpoint_slug="agt-100",
            system_prompt="Support agent",
            model_id="gpt-4o",
            is_active=True,
        )
        wf_res = WorkflowDefinition(
            id="wf-100",
            hub_id="wf-hub-1",
            name="Target Workflow",
            slug="target-wf",
            status="published",
        )
        session.add_all([agent_res, wf_res])

        link_agent = HubLink(id="l-1", source_hub_id="eval-hub-1", target_hub_id="agent-hub-1", access_level="read")
        link_wf = HubLink(id="l-2", source_hub_id="eval-hub-1", target_hub_id="wf-hub-1", access_level="read")
        session.add_all([link_agent, link_wf])

        await session.commit()
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_and_list_suites_hub_isolated(async_session: AsyncSession):
    session = async_session

    target = EvalTarget(type="agent", target_hub_id="agent-hub-1", target_id="agt-100")
    suite1 = await manager.create_suite(
        session, hub_id="eval-hub-1", name="Regression Suite", description="Test suite", target=target
    )

    assert suite1.id is not None
    assert suite1.hub_id == "eval-hub-1"

    # Listing in eval-hub-1 returns suite
    suites1 = await manager.list_suites(session, hub_id="eval-hub-1")
    assert len(suites1) == 1
    assert suites1[0].name == "Regression Suite"

    # Listing in another hub returns empty list
    suites2 = await manager.list_suites(session, hub_id="other-hub")
    assert len(suites2) == 0

    # Cross-hub get returns None
    s_cross = await manager.get_suite(session, hub_id="other-hub", suite_id=suite1.id)
    assert s_cross is None


@pytest.mark.asyncio
async def test_duplicate_suite_name_collision(async_session: AsyncSession):
    session = async_session

    target = EvalTarget(type="agent", target_hub_id="agent-hub-1", target_id="agt-100")
    await manager.create_suite(session, hub_id="eval-hub-1", name="Benchmark Suite", target=target)

    with pytest.raises(ValueError) as exc:
        await manager.create_suite(session, hub_id="eval-hub-1", name="Benchmark Suite", target=target)
    assert "SUITE_NAME_TAKEN" in str(exc.value)


@pytest.mark.asyncio
async def test_retarget_blocked_with_completed_runs(async_session: AsyncSession):
    session = async_session

    target_agent = EvalTarget(type="agent", target_hub_id="agent-hub-1", target_id="agt-100")
    target_wf = EvalTarget(type="workflow", target_hub_id="wf-hub-1", target_id="wf-100")

    suite = await manager.create_suite(session, hub_id="eval-hub-1", name="Retarget Suite", target=target_agent)

    # Seed a completed run history record
    run_hist = EvalRunHistory(
        id="run-completed-1",
        hub_id="eval-hub-1",
        target_type="agent",
        target_hub_id="agent-hub-1",
        target_id="agt-100",
        suite_id=suite.id,
        run_status="completed",
    )
    session.add(run_hist)
    await session.commit()

    # Retargeting should raise error
    with pytest.raises(ValueError) as exc:
        await manager.update_suite(session, hub_id="eval-hub-1", suite_id=suite.id, target=target_wf)
    assert "SUITE_HAS_RUNS_RETARGET_BLOCKED" in str(exc.value)


@pytest.mark.asyncio
async def test_csv_json_import_export_roundtrip(async_session: AsyncSession):
    session = async_session

    target = EvalTarget(type="workflow", target_hub_id="wf-hub-1", target_id="wf-100")
    suite = await manager.create_suite(session, hub_id="eval-hub-1", name="Import Export Suite", target=target)

    csv_data = f"""input_query,expected_output,node_id,assertion_type,expected_value
What is ContAIned?,Platform docs,node-router,contains,Platform
"""
    imported_count = await manager.import_cases_from_csv(session, hub_id="eval-hub-1", suite_id=suite.id, csv_content=csv_data)
    assert imported_count == 1

    cases = await manager.list_test_cases(session, hub_id="eval-hub-1", suite_id=suite.id)
    assert len(cases) == 1
    assert cases[0].node_id == "node-router"
    assert cases[0].assertion_type == "contains"

    # Export to JSON
    json_bytes = await manager.export_suite(session, hub_id="eval-hub-1", suite_id=suite.id, fmt="json")
    json_obj = json.loads(json_bytes.decode("utf-8"))
    assert json_obj["suite"]["id"] == suite.id
    assert len(json_obj["cases"]) == 1


@pytest.mark.asyncio
async def test_import_foreign_suite_id_rejected(async_session: AsyncSession):
    session = async_session

    target = EvalTarget(type="agent", target_hub_id="agent-hub-1", target_id="agt-100")
    suite = await manager.create_suite(session, hub_id="eval-hub-1", name="Foreign Suite Test", target=target)

    csv_foreign = f"""suite_id,input_query,expected_output
foreign-suite-999,What is AI?,Artificial Intelligence
"""
    with pytest.raises(ValueError) as exc:
        await manager.import_cases_from_csv(session, hub_id="eval-hub-1", suite_id=suite.id, csv_content=csv_foreign)
    assert "CROSS_HUB_SUITE_ID" in str(exc.value)


@pytest.mark.asyncio
async def test_synthetic_test_case_generation(async_session: AsyncSession):
    session = async_session

    target = EvalTarget(type="agent", target_hub_id="agent-hub-1", target_id="agt-100")
    cases = await synthetic.generate_synthetic_test_cases(
        session, hub_id="eval-hub-1", target=target, count=2
    )

    assert len(cases) > 0
    assert cases[0].input_query is not None
