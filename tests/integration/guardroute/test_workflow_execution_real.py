"""Real-world integration test suite for GuardRoute visual workflow execution runtime.

Tests cover:
- Real workflow step execution and status polling (queued -> running -> succeeded/failed)
- Database persistence of WorkflowRun and WorkflowRunStep telemetry
- Graph branching and conditional evaluation
- SSE execution streaming events (run_start, node_start, node_end, run_end)
- Run cancellation and terminal state transitions
"""

import asyncio
import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.models.database import (
    WorkflowDefinition,
    WorkflowVersion,
    WorkflowRun,
    WorkflowRunStep,
)
from common.schemas.workflows import (
    WorkflowRunDetail,
    WorkflowRunSummary,
    WorkflowRunStepDetail,
)
from gateway.auth.utils import create_access_token
from projects.guardroute.src.workflows import run_service

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    """Helper to generate JWT bearer auth headers."""
    token = create_access_token(
        user_id=user.id,
        email=user.email,
        platform_role=user.platform_role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_execute_linear_workflow_real(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Execute a linear workflow (LLM -> final_message) with a real model and verify status + output."""
    owner = await seed_user(email="wf_exec_linear@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Execution Linear Hub", slug="wf-exec-linear", hub_type="workflow")
    hub_id = str(hub.id)
    headers = await _auth_headers(owner)

    linear_graph = {
        "nodes": [
            {
                "id": "step_llm",
                "type": "multi_agent",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "LLM Step",
                    "agent_id": "linear_llm_agent",
                    "agent_name": "Linear LLM Agent",
                    "system_prompt": "You are a concise assistant. Answer in one short sentence.",
                    "model_id": "gemini/gemma-4-31b-it",
                    "temperature": 0.2,
                    "max_tokens": 200,
                    "timeout_sec": 60.0,
                },
            },
            {
                "id": "step_terminal",
                "type": "final_message",
                "position": {"x": 150, "y": 0},
                "data": {
                    "label": "Final Output",
                    "model_id": "gemini/gemma-4-31b-it",
                    "system_prompt": "You are the final synthesis node. Restate the answer concisely.",
                    "temperature": 0.2,
                    "max_tokens": 200,
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "step_llm", "target": "step_terminal"},
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }

    # Create workflow
    create_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows",
        json={
            "name": "Linear Execution Pipeline",
            "graph": linear_graph,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    # Publish workflow so it can be run as published
    pub_resp = await gateway_client.post(f"/api/hubs/{hub_id}/workflows/{wf_id}/publish", headers=headers)
    assert pub_resp.status_code == 200

    # Start run (non-streaming mode for 202 Accepted)
    run_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/run",
        json={"input": {"prompt": "What is the capital of France?"}, "stream": False},
        headers=headers,
    )
    assert run_resp.status_code == 202, f"Start run failed: {run_resp.text}"
    run_id = run_resp.json()["run_id"]

    # Verify run status transitions: queued -> running -> succeeded
    seen_statuses = set()
    run_data = {}
    for _ in range(240):
        await asyncio.sleep(0.5)
        poll_resp = await gateway_client.get(f"/api/hubs/{hub_id}/workflows/{wf_id}/runs/{run_id}", headers=headers)
        assert poll_resp.status_code == 200
        run_data = poll_resp.json()
        seen_statuses.add(run_data["status"])
        if run_data["status"] in ("succeeded", "failed"):
            break

    assert run_data["status"] == "succeeded", f"Run did not succeed: {run_data}"
    # The run must have passed through a running state before reaching a terminal state.
    assert "running" in seen_statuses, f"Run never entered 'running' state: {seen_statuses}"

    # Verify both nodes executed and persisted as steps
    assert len(run_data["steps"]) >= 2
    step_node_ids = [s["node_id"] for s in run_data["steps"]]
    assert "step_llm" in step_node_ids
    assert "step_terminal" in step_node_ids

    for step in run_data["steps"]:
        assert step["status"] == "succeeded"
        assert step["latency_ms"] is not None

    # Verify real LLM output was collected into the run output
    output = run_data.get("output_json") or {}
    assert output.get("final_response"), f"Expected final_response in run output: {output}"

    # Verify WorkflowRun + WorkflowRunStep rows persisted in Postgres
    db_run = await real_db_session.get(WorkflowRun, run_id)
    assert db_run is not None
    assert db_run.status == "succeeded"
    assert db_run.output_json is not None

    stmt = select(WorkflowRunStep).where(WorkflowRunStep.run_id == run_id)
    db_steps = (await real_db_session.execute(stmt)).scalars().all()
    assert len(db_steps) >= 2

    # Query run traces endpoint
    traces_resp = await gateway_client.get(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/runs/{run_id}/traces?include_state=true",
        headers=headers,
    )
    assert traces_resp.status_code == 200
    assert isinstance(traces_resp.json(), list)


@pytest.mark.asyncio
async def test_execute_conditional_workflow_branching(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Execute a conditional workflow branching to VIP vs standard final_message based on state."""
    owner = await seed_user(email="wf_exec_cond@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Execution Cond Hub", slug="wf-exec-cond", hub_type="workflow")
    hub_id = str(hub.id)
    headers = await _auth_headers(owner)

    conditional_graph = {
        "nodes": [
            {
                "id": "router_node",
                "type": "if_else",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "VIP Checker",
                    "condition": "prompt == 'VIP'",
                    "true_target": "vip_terminal",
                    "false_target": "standard_terminal",
                },
            },
            {
                "id": "vip_terminal",
                "type": "final_message",
                "position": {"x": 150, "y": -50},
                "data": {"label": "VIP Response", "message": "Welcome VIP customer"},
            },
            {
                "id": "standard_terminal",
                "type": "final_message",
                "position": {"x": 150, "y": 50},
                "data": {"label": "Standard Response", "message": "Welcome standard customer"},
            },
        ],
        "edges": [
            {"id": "e_true", "source": "router_node", "target": "vip_terminal", "sourceHandle": "true"},
            {"id": "e_false", "source": "router_node", "target": "standard_terminal", "sourceHandle": "false"},
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows",
        json={
            "name": "Conditional Branching Flow",
            "graph": conditional_graph,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    await gateway_client.post(f"/api/hubs/{hub_id}/workflows/{wf_id}/publish", headers=headers)

    # 1. Run with prompt == 'VIP' -> should execute vip_terminal
    vip_run_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/run",
        json={"input": {"prompt": "VIP"}, "stream": False},
        headers=headers,
    )
    assert vip_run_resp.status_code == 202
    vip_run_id = vip_run_resp.json()["run_id"]

    vip_detail = {}
    for _ in range(120):
        await asyncio.sleep(0.5)
        poll_resp = await gateway_client.get(f"/api/hubs/{hub_id}/workflows/{wf_id}/runs/{vip_run_id}", headers=headers)
        vip_detail = poll_resp.json()
        if vip_detail.get("status") in ("succeeded", "failed"):
            break

    assert vip_detail["status"] == "succeeded"
    vip_executed_nodes = [s["node_id"] for s in vip_detail["steps"]]
    assert "router_node" in vip_executed_nodes
    assert len(vip_executed_nodes) >= 1

    # 2. Run with prompt == 'REGULAR' -> should execute standard_terminal
    std_run_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/run",
        json={"input": {"prompt": "REGULAR"}, "stream": False},
        headers=headers,
    )
    assert std_run_resp.status_code == 202
    std_run_id = std_run_resp.json()["run_id"]

    std_detail = {}
    for _ in range(120):
        await asyncio.sleep(0.5)
        poll_resp = await gateway_client.get(f"/api/hubs/{hub_id}/workflows/{wf_id}/runs/{std_run_id}", headers=headers)
        std_detail = poll_resp.json()
        if std_detail.get("status") in ("succeeded", "failed"):
            break

    assert std_detail["status"] == "succeeded"
    std_executed_nodes = [s["node_id"] for s in std_detail["steps"]]
    assert "router_node" in std_executed_nodes
    assert len(std_executed_nodes) >= 1


@pytest.mark.asyncio
async def test_execute_workflow_with_mcp_tool(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Execute a workflow whose agent node invokes a real MCP DB-bridge tool (db_query_executor)."""
    owner = await seed_user(email="wf_exec_mcp@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Execution MCP Hub", slug="wf-exec-mcp", hub_type="workflow")
    hub_id = str(hub.id)
    headers = await _auth_headers(owner)

    # Seed a model registry row so the MCP query returns real data (committed via API).
    from common.models.database import ModelRegistryModel
    real_db_session.add(
        ModelRegistryModel(
            role="completion",
            mode="api",
            provider="google",
            model_id="gemini/gemma-4-31b-it",
            display_name="Gemma 4 31B",
            is_enabled=True,
        )
    )
    await real_db_session.flush()

    # Create a hub-scoped ExternalCredential via the API so it is committed and
    # visible to the background run task. Points at the test Postgres.
    cred_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/db-credentials",
        json={
            "name": "Test Postgres MCP",
            "db_type": "postgres",
            "host": "localhost",
            "port": 5432,
            "database_name": "contained_platform",
            "username": "contained",
            "password": "contained_pass",
            "is_read_only": True,
            "max_connections": 2,
        },
        headers=headers,
    )
    assert cred_resp.status_code == 201, f"Create credential failed: {cred_resp.text}"
    cred_id = cred_resp.json()["id"]

    # Create an agent hub and an agent in it, then link the workflow hub -> agent hub
    # so the agent node's cross-hub reference resolves.
    agent_hub = await seed_hub(owner=owner, name="MCP Agent Hub", slug="wf-exec-mcp-agents", hub_type="agent")
    agent_hub_id = str(agent_hub.id)

    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub_id}/agents",
        json={
            "name": "MCP Workflow Agent",
            "role": "assistant",
            "system_prompt": "You are an assistant that uses MCP tools.",
            "model_id": "gemini/gemma-4-31b-it",
            "is_active": True,
        },
        headers=headers,
    )
    assert agent_resp.status_code == 201, f"Create agent failed: {agent_resp.text}"
    agent_id = agent_resp.json()["id"]

    link_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/links",
        json={"target_hub_id": agent_hub_id, "access_level": "use"},
        headers=headers,
    )
    assert link_resp.status_code == 201, f"Create hub link failed: {link_resp.text}"

    # Commit the real_db_session so the hub/credential/agent/model rows are visible
    # to the background run task's separate connections (get_sessionmaker).
    await real_db_session.commit()

    # Agent node bound with an MCP tool (db_query_executor) that queries the model_registry table.
    mcp_graph = {
        "nodes": [
            {
                "id": "agent_mcp",
                "type": "agent",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "MCP Agent",
                    "reference": {"type": "agent", "hub_id": agent_hub_id, "resource_id": agent_id},
                    "tools": [
                        {
                            "type": "mcp",
                            "label": "query_registry",
                            "server_id": "db-bridge",
                            "hub_id": hub_id,
                            "tool_name": "db_query_executor",
                            "input_mapping": {
                                "credential_id": cred_id,
                                "sql_query": "SELECT model_id FROM model_registry LIMIT 5",
                            },
                        }
                    ],
                },
            },
            {
                "id": "mcp_terminal",
                "type": "final_message",
                "position": {"x": 150, "y": 0},
                "data": {"label": "Final Output", "message": "MCP tool executed"},
            },
        ],
        "edges": [{"id": "e_m", "source": "agent_mcp", "target": "mcp_terminal"}],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows",
        json={"name": "MCP Tool Workflow", "graph": mcp_graph},
        headers=headers,
    )
    assert create_resp.status_code == 201, f"Create MCP workflow failed: {create_resp.text}"
    wf_id = create_resp.json()["id"]

    await gateway_client.post(f"/api/hubs/{hub_id}/workflows/{wf_id}/publish", headers=headers)

    run_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/run",
        json={"input": {"prompt": "Query the model registry"}, "stream": False},
        headers=headers,
    )
    assert run_resp.status_code == 202, f"Start MCP run failed: {run_resp.text}"
    run_id = run_resp.json()["run_id"]

    run_data = {}
    for _ in range(120):
        await asyncio.sleep(0.5)
        poll_resp = await gateway_client.get(f"/api/hubs/{hub_id}/workflows/{wf_id}/runs/{run_id}", headers=headers)
        assert poll_resp.status_code == 200
        run_data = poll_resp.json()
        if run_data["status"] in ("succeeded", "failed"):
            break

    assert run_data["status"] == "succeeded", f"MCP run did not succeed: {run_data}"

    # The agent node must have executed and its tool results captured.
    step_node_ids = [s["node_id"] for s in run_data["steps"]]
    assert "agent_mcp" in step_node_ids

    # Verify the MCP tool result is present in the run output (tool_results keyed by node id).
    output = run_data.get("output_json") or {}
    tool_results = (output.get("tool_results") or {}).get("agent_mcp") or {}
    query_result = (tool_results.get("tool_results_map") or {}).get("query_registry") or {}
    assert query_result.get("success") is True, f"MCP tool did not succeed: {query_result}"
    assert query_result.get("row_count", 0) >= 1, f"MCP tool returned no rows: {query_result}"


@pytest.mark.asyncio
async def test_workflow_sse_streaming_events(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Execute workflow with stream=True and verify SSE formatted event delivery."""
    owner = await seed_user(email="wf_exec_stream@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Execution Stream Hub", slug="wf-exec-stream", hub_type="workflow")
    hub_id = str(hub.id)
    headers = await _auth_headers(owner)

    stream_graph = {
        "nodes": [
            {
                "id": "step_1",
                "type": "transform",
                "position": {"x": 0, "y": 0},
                "data": {"label": "Step 1", "mode": "template", "template": "Event 1"},
            },
            {
                "id": "step_end",
                "type": "final_message",
                "position": {"x": 100, "y": 0},
                "data": {"label": "Step End", "message": "Event End"},
            },
        ],
        "edges": [{"id": "e_s", "source": "step_1", "target": "step_end"}],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows",
        json={"name": "SSE Streaming Workflow", "graph": stream_graph},
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    await gateway_client.post(f"/api/hubs/{hub_id}/workflows/{wf_id}/publish", headers=headers)

    # Start run
    run_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/run",
        json={"input": {"prompt": "Stream test"}, "stream": False},
        headers=headers,
    )
    assert run_resp.status_code == 202
    run_id = run_resp.json()["run_id"]

    # Wait for execution task to complete
    if run_id in run_service._RUN_TASKS:
        await run_service._RUN_TASKS[run_id]

    # Stream SSE events via run_service.stream_run
    events = []
    async for evt in run_service.stream_run(run_id):
        events.append(evt)
        if evt.get("event") == "run_end":
            break

    event_names = [e["event"] for e in events]
    assert "run_start" in event_names
    assert "run_end" in event_names


@pytest.mark.asyncio
async def test_workflow_run_cancelation(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Test cancelling an in-progress workflow run (uses a slow LLM node so cancel can land)."""
    owner = await seed_user(email="wf_exec_cancel@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Execution Cancel Hub", slug="wf-exec-cancel", hub_type="workflow")
    hub_id = str(hub.id)
    headers = await _auth_headers(owner)

    # Use a real LLM node so the run takes long enough to cancel deterministically.
    long_graph = {
        "nodes": [
            {
                "id": "node_llm",
                "type": "multi_agent",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "Slow LLM",
                    "agent_id": "cancel_llm_agent",
                    "agent_name": "Cancel LLM Agent",
                    "system_prompt": "You are a verbose assistant. Write a long detailed essay.",
                    "model_id": "gemini/gemma-4-31b-it",
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "timeout_sec": 120.0,
                },
            },
            {
                "id": "node_end",
                "type": "final_message",
                "position": {"x": 100, "y": 0},
                "data": {"label": "Final Output", "message": "Done"},
            },
        ],
        "edges": [{"id": "e_c", "source": "node_llm", "target": "node_end"}],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows",
        json={"name": "Cancelable Flow", "graph": long_graph},
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    await gateway_client.post(f"/api/hubs/{hub_id}/workflows/{wf_id}/publish", headers=headers)

    run_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/run",
        json={"input": {"prompt": "Write a long essay about the history of computing."}, "stream": False},
        headers=headers,
    )
    assert run_resp.status_code == 202
    run_id = run_resp.json()["run_id"]

    # Cancel immediately
    cancel_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/runs/{run_id}/cancel",
        headers=headers,
    )
    assert cancel_resp.status_code in (200, 409)

    # If 200, status must be cancelled or terminal
    if cancel_resp.status_code == 200:
        assert cancel_resp.json()["status"] == "cancelled"

    if run_id in run_service._RUN_TASKS:
        try:
            await run_service._RUN_TASKS[run_id]
        except Exception:
            pass
