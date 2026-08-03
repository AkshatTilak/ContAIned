"""Integration tests for Eval Hub API routes & dashboard aggregations (S6-07e)."""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from common.clients.postgres import get_async_db
from common.config.settings import get_settings


@pytest.fixture(autouse=True)
def disable_auth(monkeypatch):
    monkeypatch.setattr(get_settings(), "AUTH_ENABLED", False)
from common.models.database import (
    AgentDefinition,
    Base,
    EvalFlowTrace,
    EvalMetricResult,
    EvalRunHistory,
    EvalTestCase,
    EvalTestSuite,
    Hub,
    HubLink,
    HubMember,
    User,
    WorkflowDefinition,
)
from gateway.api.eval_hub import router as eval_hub_router
from gateway.auth.hub_context import HubContext, require_hub


@pytest_asyncio.fixture
async def app_and_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        # Seed users
        u_owner = User(id="usr-owner", email="owner@example.com", platform_role="admin", status="active")
        u_member = User(id="usr-member", email="member@example.com", platform_role="member", status="active")
        session.add_all([u_owner, u_member])

        # Seed hubs
        eval_hub = Hub(id="hub-eval", slug="eval", name="Eval Hub", hub_type="eval", owner_id="usr-owner")
        agent_hub = Hub(id="hub-agent", slug="agent", name="Agent Hub", hub_type="agent", owner_id="usr-owner")
        wf_hub = Hub(id="hub-wf", slug="wf", name="Workflow Hub", hub_type="workflow", owner_id="usr-owner")
        session.add_all([eval_hub, agent_hub, wf_hub])

        # Memberships: owner is owner, member is viewer
        session.add(HubMember(hub_id="hub-eval", user_id="usr-owner", hub_role="owner"))
        session.add(HubMember(hub_id="hub-eval", user_id="usr-member", hub_role="viewer"))

        # Target resources
        ag = AgentDefinition(id="ag-1", hub_id="hub-agent", name="Agent 1", role="assistant", system_prompt="Hi", model_id="gpt-4o")
        wf = WorkflowDefinition(id="wf-1", hub_id="hub-wf", name="Workflow 1", slug="wf-1", status="published")
        session.add_all([ag, wf])

        # Links
        session.add(HubLink(id="l-1", source_hub_id="hub-eval", target_hub_id="hub-agent", access_level="read"))
        session.add(HubLink(id="l-2", source_hub_id="hub-eval", target_hub_id="hub-wf", access_level="read"))

        # Suite & Run history
        suite = EvalTestSuite(id="s-1", hub_id="hub-eval", name="Main Suite", target_type="workflow", target_hub_id="hub-wf", target_id="wf-1")
        case = EvalTestCase(id="c-1", suite_id="s-1", input_query="Query", node_id="node-1", assertion_type="equals", expected_value="val")
        run_hist = EvalRunHistory(id="r-1", hub_id="hub-eval", target_type="workflow", target_hub_id="hub-wf", target_id="wf-1", suite_id="s-1", workflow_run_id="wfr-1", run_status="completed", faithfulness_score=0.95, relevance_score=0.90, total_test_cases=1, passed_count=1, failed_count=0, duration_sec=1.5)
        trace = EvalFlowTrace(id="t-1", hub_id="hub-eval", run_id="wfr-1", node_id="node-1", node_type="ClassifierNode", sequence=1, latency_ms=120.0, output_state={"val": "val"})
        metric_res = EvalMetricResult(id="m-1", run_id="r-1", test_case_id="c-1", node_id="node-1", assertion_type="equals", metric_name="node_assertion.node-1.equals", metric_score=1.0, framework="node_assertion", passed=True)
        session.add_all([suite, case, run_hist, trace, metric_res])

        await session.commit()

    # Override async db dependency
    async def override_get_db():
        async with session_factory() as s:
            yield s

    # App setup
    test_app = FastAPI()
    test_app.include_router(eval_hub_router, prefix="/api")
    test_app.dependency_overrides[get_async_db] = override_get_db

    yield test_app, session_factory

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_targets_feed(app_and_session):
    test_app, session_factory = app_and_session
    client = TestClient(test_app)

    # Mock HubContext dependency
    async def mock_context():
        return HubContext(
            hub=Hub(id="hub-eval", slug="eval", name="Eval Hub", hub_type="eval", owner_id="usr-owner"),
            user=User(id="usr-owner", email="owner@example.com", platform_role="admin", status="active"),
            member=HubMember(hub_id="hub-eval", user_id="usr-owner", hub_role="owner"),
            role="owner",
        )

    test_app.dependency_overrides[require_hub(hub_type="eval", min_role="viewer")] = mock_context

    response = client.get("/api/hubs/hub-eval/eval/targets")
    assert response.status_code == 200
    targets = response.json()
    assert len(targets) == 2
    types = [t["type"] for t in targets]
    assert "agent" in types
    assert "workflow" in types


@pytest.mark.asyncio
async def test_get_suites_and_cases(app_and_session):
    test_app, session_factory = app_and_session
    client = TestClient(test_app)

    async def mock_context():
        return HubContext(
            hub=Hub(id="hub-eval", slug="eval", name="Eval Hub", hub_type="eval", owner_id="usr-owner"),
            user=User(id="usr-owner", email="owner@example.com", platform_role="admin", status="active"),
            member=HubMember(hub_id="hub-eval", user_id="usr-owner", hub_role="owner"),
            role="owner",
        )

    test_app.dependency_overrides[require_hub(hub_type="eval", min_role="viewer")] = mock_context

    # Get suite
    res_s = client.get("/api/hubs/hub-eval/eval/suites/s-1")
    assert res_s.status_code == 200
    assert res_s.json()["name"] == "Main Suite"

    # Get cases
    res_c = client.get("/api/hubs/hub-eval/eval/suites/s-1/cases")
    assert res_c.status_code == 200
    cases = res_c.json()
    assert len(cases) == 1
    assert cases[0]["node_id"] == "node-1"


@pytest.mark.asyncio
async def test_dashboard_stats_and_traces(app_and_session):
    test_app, session_factory = app_and_session
    client = TestClient(test_app)

    async def mock_context():
        return HubContext(
            hub=Hub(id="hub-eval", slug="eval", name="Eval Hub", hub_type="eval", owner_id="usr-owner"),
            user=User(id="usr-owner", email="owner@example.com", platform_role="admin", status="active"),
            member=HubMember(hub_id="hub-eval", user_id="usr-owner", hub_role="owner"),
            role="owner",
        )

    test_app.dependency_overrides[require_hub(hub_type="eval", min_role="viewer")] = mock_context

    # Stats
    res_st = client.get("/api/hubs/hub-eval/eval/dashboard/stats")
    assert res_st.status_code == 200
    stats = res_st.json()
    assert stats["total_runs"] == 1
    assert stats["metrics"]["faithfulness"] == 0.95

    # Traces
    res_tr = client.get("/api/hubs/hub-eval/eval/runs/r-1/traces")
    assert res_tr.status_code == 200
    traces = res_tr.json()
    assert len(traces["nodes"]) == 1
    assert traces["nodes"][0]["node_id"] == "node-1"
    assert len(traces["nodes"][0]["assertions"]) == 1
    assert traces["nodes"][0]["assertions"][0]["passed"] is True
