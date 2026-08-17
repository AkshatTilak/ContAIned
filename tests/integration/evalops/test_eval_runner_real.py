"""Real-world integration test suite for EvalOps Evaluation Runner against real Postgres and LLM.

Covers synchronous and asynchronous evaluation run dispatching against polymorphic
targets (Agents & Workflows), metric computation (DeepEval / RAGAS / Node Assertions),
run lifecycle tracking, trace replays, and score retrieval.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import EvalMetricResult, EvalRunHistory, EvalTestSuite
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    """Build Authorization header for a seeded user."""
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_sync_eval_run_agent_target_real(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Dispatch synchronous evaluation against an active Agent target, verify metrics and DB records."""
    owner = await seed_user(email="eval_runner_owner@contained.ai", role="member")
    headers = await _auth_headers(owner)

    # 1. Seed Agent Hub and Agent
    agent_hub = await seed_hub(owner=owner, name="Eval Target Agent Hub", slug="eval-target-agent-hub", hub_type="agent")
    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/agents",
        json={
            "name": "Geography Expert",
            "role": "expert",
            "system_prompt": "You are a concise geography expert. Answer queries with direct factual answers.",
            "model_id": "gemini/gemma-4-31b-it",
            "temperature": 0.1,
            "is_active": True,
        },
        headers=headers,
    )
    assert agent_resp.status_code == 201, f"Create agent failed: {agent_resp.text}"
    agent = agent_resp.json()

    # 2. Seed Eval Hub and link to Agent Hub
    eval_hub = await seed_hub(owner=owner, name="Runner Eval Hub", slug="runner-eval-hub", hub_type="eval")
    link_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/links",
        json={"target_hub_id": agent_hub.id, "access_level": "read"},
        headers=headers,
    )
    assert link_resp.status_code == 201

    # 3. Create Test Suite
    suite_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites",
        json={
            "name": "Geography Knowledge Suite",
            "description": "Factual recall evaluation",
            "target": {
                "type": "agent",
                "target_hub_id": agent_hub.id,
                "target_id": agent["id"],
            },
        },
        headers=headers,
    )
    assert suite_resp.status_code == 201
    suite_id = suite_resp.json()["id"]

    # 4. Add Test Cases
    await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases",
        json={
            "input_query": "What is the capital of France?",
            "expected_output": "The capital of France is Paris.",
            "expected_context": "France is a country in Western Europe whose capital city is Paris.",
            "node_id": "agent_response",
            "assertion_type": "contains",
            "expected_value": "Paris",
        },
        headers=headers,
    )
    await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases",
        json={
            "input_query": "What is the highest mountain on Earth?",
            "expected_output": "Mount Everest is the highest mountain.",
            "expected_context": "Mount Everest is Earth's highest mountain above sea level.",
            "node_id": "agent_response",
            "assertion_type": "contains",
            "expected_value": "Everest",
        },
        headers=headers,
    )

    # 5. Trigger Synchronous Evaluation Run
    run_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/runs?async=false",
        json={
            "suite_id": suite_id,
            "framework": "both",
        },
        headers=headers,
    )
    assert run_resp.status_code == 202, f"Trigger eval run failed: {run_resp.text}"
    run_data = run_resp.json()
    assert run_data["run_status"] == "completed"
    assert run_data["suite_id"] == suite_id
    run_id = run_data["id"]

    # 6. Verify EvalRunHistory in DB
    run_history_stmt = select(EvalRunHistory).where(EvalRunHistory.id == run_id)
    history_row = (await real_db_session.execute(run_history_stmt)).scalar_one_or_none()
    assert history_row is not None
    assert history_row.run_status == "completed"
    assert history_row.total_test_cases == 2
    assert history_row.passed_count >= 1
    assert history_row.duration_sec is not None and history_row.duration_sec > 0
    assert history_row.faithfulness_score is not None
    assert history_row.relevance_score is not None

    # 7. Verify Metric Results in DB
    metrics_stmt = select(EvalMetricResult).where(EvalMetricResult.run_id == run_id)
    metric_rows = (await real_db_session.execute(metrics_stmt)).scalars().all()
    assert len(metric_rows) > 0


@pytest.mark.asyncio
async def test_eval_run_retrieval_and_filtering_real(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Verify run history retrieval endpoints, single run inspection, and query filtering."""
    owner = await seed_user(email="run_inspector@contained.ai", role="member")
    headers = await _auth_headers(owner)

    agent_hub = await seed_hub(owner=owner, name="Inspector Agent Hub", slug="inspector-agent-hub", hub_type="agent")
    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/agents",
        json={
            "name": "Math Agent",
            "role": "math",
            "system_prompt": "You are a concise mathematician.",
            "model_id": "gemini/gemma-4-26b-a4b-it",
        },
        headers=headers,
    )
    agent = agent_resp.json()

    eval_hub = await seed_hub(owner=owner, name="Inspector Eval Hub", slug="inspector-eval-hub", hub_type="eval")
    await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/links",
        json={"target_hub_id": agent_hub.id, "access_level": "read"},
        headers=headers,
    )

    suite_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites",
        json={
            "name": "Arithmetic Suite",
            "target": {"type": "agent", "target_hub_id": agent_hub.id, "target_id": agent["id"]},
        },
        headers=headers,
    )
    suite_id = suite_resp.json()["id"]

    await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases",
        json={
            "input_query": "What is 2 + 2?",
            "expected_output": "4",
            "node_id": "math_node",
            "assertion_type": "contains",
            "expected_value": "4",
        },
        headers=headers,
    )

    # Trigger run
    trigger_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/runs?async=false",
        json={"suite_id": suite_id},
        headers=headers,
    )
    assert trigger_resp.status_code == 202
    run_id = trigger_resp.json()["id"]

    # 1. List all runs
    list_runs_resp = await gateway_client.get(
        f"/api/hubs/{eval_hub.id}/eval/runs",
        headers=headers,
    )
    assert list_runs_resp.status_code == 200
    runs = list_runs_resp.json()
    assert len(runs) >= 1
    assert any(r["id"] == run_id for r in runs)

    # 2. Filter runs by suite_id
    filtered_resp = await gateway_client.get(
        f"/api/hubs/{eval_hub.id}/eval/runs?suite_id={suite_id}",
        headers=headers,
    )
    assert filtered_resp.status_code == 200
    f_runs = filtered_resp.json()
    assert len(f_runs) >= 1
    assert all(r["suite_id"] == suite_id for r in f_runs)

    # 3. Get single run details
    single_run_resp = await gateway_client.get(
        f"/api/hubs/{eval_hub.id}/eval/runs/{run_id}",
        headers=headers,
    )
    assert single_run_resp.status_code == 200
    run_detail = single_run_resp.json()
    assert run_detail["id"] == run_id
    assert run_detail["status"] == "completed"
    assert "faithfulness_score" in run_detail
    assert "relevance_score" in run_detail


@pytest.mark.asyncio
async def test_eval_run_workflow_target_and_trace_replay_real(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Execute eval against a workflow target and inspect trace replay outputs."""
    owner = await seed_user(email="wf_eval_owner@contained.ai", role="member")
    headers = await _auth_headers(owner)

    # 1. Create Workflow Hub and Workflow
    wf_hub = await seed_hub(owner=owner, name="Workflow Source Hub", slug="wf-source-hub", hub_type="workflow")
    wf_create_resp = await gateway_client.post(
        f"/api/hubs/{wf_hub.id}/workflows",
        json={
            "name": "QA Pipeline Workflow",
            "description": "Linear QA pipeline",
            "canvas_nodes": [
                {"id": "input-1", "type": "input", "data": {"label": "Start"}},
                {"id": "transform-1", "type": "transform", "data": {"expression": "upper(prompt)"}},
                {"id": "output-1", "type": "terminal", "data": {"label": "End"}},
            ],
            "canvas_edges": [
                {"id": "e1", "source": "input-1", "target": "transform-1"},
                {"id": "e2", "source": "transform-1", "target": "output-1"},
            ],
        },
        headers=headers,
    )
    assert wf_create_resp.status_code == 201, f"Create workflow failed: {wf_create_resp.text}"
    wf_data = wf_create_resp.json()
    wf_id = wf_data["id"]

    # 2. Create Eval Hub and link to Workflow Hub
    eval_hub = await seed_hub(owner=owner, name="WF Eval Hub", slug="wf-eval-hub", hub_type="eval")
    link_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/links",
        json={"target_hub_id": wf_hub.id, "access_level": "read"},
        headers=headers,
    )
    assert link_resp.status_code == 201

    # 3. Create Suite targeting Workflow
    suite_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites",
        json={
            "name": "Pipeline Transformation Suite",
            "target": {
                "type": "workflow",
                "target_hub_id": wf_hub.id,
                "target_id": wf_id,
            },
        },
        headers=headers,
    )
    assert suite_resp.status_code == 201
    suite_id = suite_resp.json()["id"]

    # 4. Add case with node assertion
    await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases",
        json={
            "input_query": "hello world",
            "expected_output": "HELLO WORLD",
            "node_id": "output-1",
            "assertion_type": "contains",
            "expected_value": "HELLO",
        },
        headers=headers,
    )

    # 5. Dispatch Evaluation Run
    run_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/runs?async=false",
        json={"suite_id": suite_id},
        headers=headers,
    )
    assert run_resp.status_code == 202
    run_id = run_resp.json()["id"]

    # 6. Query traces replay endpoint
    trace_resp = await gateway_client.get(
        f"/api/hubs/{eval_hub.id}/eval/runs/{run_id}/traces?include_state=true",
        headers=headers,
    )
    assert trace_resp.status_code == 200
    trace_data = trace_resp.json()
    assert trace_data["run_id"] == run_id
    assert trace_data["target"]["type"] == "workflow"
    assert "nodes" in trace_data


@pytest.mark.asyncio
async def test_empty_suite_and_async_dispatch_validation(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Verify empty suite execution is rejected and async evaluation returns 202 queued."""
    owner = await seed_user(email="async_eval_owner@contained.ai", role="member")
    headers = await _auth_headers(owner)

    agent_hub = await seed_hub(owner=owner, name="Async Agent Hub", slug="async-agent-hub", hub_type="agent")
    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/agents",
        json={
            "name": "Async Target Agent",
            "role": "assistant",
            "system_prompt": "You are a prompt evaluator assistant.",
            "model_id": "gemini/gemma-3-27b-it",
        },
        headers=headers,
    )
    agent = agent_resp.json()

    eval_hub = await seed_hub(owner=owner, name="Async Eval Hub", slug="async-eval-hub", hub_type="eval")
    await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/links",
        json={"target_hub_id": agent_hub.id, "access_level": "read"},
        headers=headers,
    )

    # 1. Create Empty Suite
    suite_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites",
        json={
            "name": "Empty Eval Suite",
            "target": {"type": "agent", "target_hub_id": agent_hub.id, "target_id": agent["id"]},
        },
        headers=headers,
    )
    suite_id = suite_resp.json()["id"]

    # 2. Attempt running empty suite -> 400 SUITE_EMPTY
    empty_run_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/runs?async=false",
        json={"suite_id": suite_id},
        headers=headers,
    )
    assert empty_run_resp.status_code == 400
    assert "SUITE_EMPTY" in empty_run_resp.text

    # 3. Add a test case
    await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/suites/{suite_id}/cases",
        json={
            "input_query": "Ping",
            "expected_output": "Pong",
            "node_id": "echo_node",
            "assertion_type": "contains",
            "expected_value": "Pong",
        },
        headers=headers,
    )

    # 4. Trigger async evaluation run -> 202 Accepted with status 'queued'
    async_run_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub.id}/eval/runs?async=true",
        json={"suite_id": suite_id},
        headers=headers,
    )
    assert async_run_resp.status_code == 202
    async_data = async_run_resp.json()
    assert async_data["run_status"] == "queued"
    assert async_data["suite_id"] == suite_id
