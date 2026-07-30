"""Master acceptance test suite for B6-07: Eval Hub — Polymorphic Targets & Flow Tracing."""

import json
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.clients.postgres import get_async_db
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
from common.schemas.evalops import EvalTarget
from gateway.api.eval_hub import router as eval_hub_router
from gateway.auth.hub_context import HubContext, require_hub
from projects.evalops.src.datasets import manager
from projects.evalops.src.runner import block_assertion_engine, dispatch, trace_reader


@pytest_asyncio.fixture
async def master_eval_setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        u_owner = User(id="user-master-owner", email="m_owner@example.com", platform_role="admin", status="active")
        session.add(u_owner)

        # Hubs: eval/alpha, eval/beta, agent/default, workflow/default
        eval_alpha = Hub(id="eval-alpha", slug="eval-alpha", name="Eval Hub Alpha", hub_type="eval", owner_id="user-master-owner")
        eval_beta = Hub(id="eval-beta", slug="eval-beta", name="Eval Hub Beta", hub_type="eval", owner_id="user-master-owner")
        agent_hub = Hub(id="agent-hub", slug="agent-hub", name="Agent Hub", hub_type="agent", owner_id="user-master-owner")
        wf_hub = Hub(id="wf-hub", slug="wf-hub", name="Workflow Hub", hub_type="workflow", owner_id="user-master-owner")
        session.add_all([eval_alpha, eval_beta, agent_hub, wf_hub])

        # Memberships
        for h_id in ["eval-alpha", "eval-beta", "agent-hub", "wf-hub"]:
            session.add(HubMember(hub_id=h_id, user_id="user-master-owner", hub_role="owner"))

        # Target resources
        ag = AgentDefinition(id="ag-alpha", hub_id="agent-hub", name="Alpha Agent", role="assistant", system_prompt="Alpha prompt", model_id="gpt-4o")
        wf = WorkflowDefinition(id="wf-alpha", hub_id="wf-hub", name="Alpha Workflow", slug="alpha-wf", status="published")
        session.add_all([ag, wf])

        # Links: eval-alpha -> agent-hub, eval-alpha -> wf-hub (eval-beta has NO links)
        l_ag = HubLink(id="link-ag", source_hub_id="eval-alpha", target_hub_id="agent-hub", access_level="read")
        l_wf = HubLink(id="link-wf", source_hub_id="eval-alpha", target_hub_id="wf-hub", access_level="read")
        session.add_all([l_ag, l_wf])

        await session.commit()
        yield session, session_factory

    await engine.dispose()


@pytest.mark.asyncio
async def test_polymorphic_targeting(master_eval_setup):
    session, _ = master_eval_setup

    # 1. Target Agent Suite
    target_agent = EvalTarget(type="agent", target_hub_id="agent-hub", target_id="ag-alpha")
    suite_ag = await manager.create_suite(session, hub_id="eval-alpha", name="Agent Benchmark", target=target_agent)
    assert suite_ag.target_type == "agent"
    assert suite_ag.target_id == "ag-alpha"

    # 2. Target Workflow Suite
    target_wf = EvalTarget(type="workflow", target_hub_id="wf-hub", target_id="wf-alpha")
    suite_wf = await manager.create_suite(session, hub_id="eval-alpha", name="Workflow Benchmark", target=target_wf)
    assert suite_wf.target_type == "workflow"
    assert suite_wf.target_id == "wf-alpha"


@pytest.mark.asyncio
async def test_link_enforcement_and_mismatch(master_eval_setup):
    session, _ = master_eval_setup

    from common.services.hub_resolver import HubLinkError

    # Unlinked hub (eval-beta) attempting to target agent-hub -> HubLinkError (403 HUB_LINK_REQUIRED)
    target_unlinked = EvalTarget(type="agent", target_hub_id="agent-hub", target_id="ag-alpha")
    with pytest.raises((HubLinkError, ValueError)) as exc1:
        await manager.create_suite(session, hub_id="eval-beta", name="Unlinked Suite", target=target_unlinked)
    assert "HUB_LINK_REQUIRED" in str(exc1.value) or "HubLinkError" in type(exc1.value).__name__

    # Cross-hub reference mismatch: target_id is wf-alpha (in wf-hub) but target_hub_id claims agent-hub
    target_mismatch = EvalTarget(type="agent", target_hub_id="agent-hub", target_id="wf-alpha")
    with pytest.raises((HubLinkError, ValueError)) as exc2:
        await manager.create_suite(session, hub_id="eval-alpha", name="Mismatch Suite", target=target_mismatch)
    assert any(
        kw in str(exc2.value)
        for kw in ("CROSS_HUB_REFERENCE_MISMATCH", "HUB_LINK_REQUIRED", "EVAL_TARGET_MISSING")
    ) or "HubLinkError" in type(exc2.value).__name__


@pytest.mark.asyncio
async def test_workflow_trace_assertions(master_eval_setup):
    session, _ = master_eval_setup

    target_wf = EvalTarget(type="workflow", target_hub_id="wf-hub", target_id="wf-alpha")
    suite = await manager.create_suite(session, hub_id="eval-alpha", name="Trace Assertion Suite", target=target_wf)

    c_pass = await manager.add_test_case(
        session,
        hub_id="eval-alpha",
        suite_id=suite.id,
        input_query="Test prompt",
        node_id="node-classifier",
        assertion_type="equals",
        assertion_config={"field_path": "category"},
        expected_value="support",
    )
    c_fail = await manager.add_test_case(
        session,
        hub_id="eval-alpha",
        suite_id=suite.id,
        input_query="Test prompt",
        node_id="nonexistent-node",
        assertion_type="contains",
        expected_value="val",
    )

    # Seed execution traces for wf-run-1
    tr1 = EvalFlowTrace(
        id="t-wf-1",
        hub_id="eval-alpha",
        run_id="wf-run-1",
        node_id="node-classifier",
        node_type="ClassifierNode",
        sequence=1,
        output_state={"category": "support"},
        latency_ms=85.0,
    )
    session.add(tr1)
    await session.commit()

    # Evaluate node assertions
    results = await block_assertion_engine.evaluate_node_assertions(
        session,
        hub_id="eval-alpha",
        run_id="wf-run-1",
        eval_run_id="eval-run-1",
        cases=[c_pass, c_fail],
    )

    assert len(results) == 2
    r_pass = next(r for r in results if r.test_case_id == c_pass.id)
    r_fail = next(r for r in results if r.test_case_id == c_fail.id)

    assert r_pass.passed is True
    assert r_fail.passed is False
    assert "NODE_NOT_EXECUTED" in r_fail.metric_reason


@pytest.mark.asyncio
async def test_dataset_safety_foreign_suite_id(master_eval_setup):
    session, _ = master_eval_setup

    target = EvalTarget(type="agent", target_hub_id="agent-hub", target_id="ag-alpha")
    suite = await manager.create_suite(session, hub_id="eval-alpha", name="CSV Safety Suite", target=target)

    csv_bad = """suite_id,input_query,expected_output
foreign-suite-id,What is AI?,Artificial Intelligence
"""
    with pytest.raises(ValueError) as exc:
        await manager.import_cases_from_csv(session, hub_id="eval-alpha", suite_id=suite.id, csv_content=csv_bad)
    assert "CROSS_HUB_SUITE_ID" in str(exc.value)
