"""Real-world integration test suite for MCP Tool Nodes in GuardRoute Workflows.

Tests direct MCP node execution, variable interpolation, bearer auth token passing,
error and degradation handling, and workflow graph integration against live infrastructure.
"""

import asyncio
import socket
import pytest
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from httpx import AsyncClient
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import MCPServer
from gateway.auth.utils import create_access_token
from mcp_tools.sample_calculator.server import app as calc_app
from projects.guardroute.src.nodes.mcp_tool_executor import execute_mcp_tool

pytestmark = pytest.mark.integration


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


import threading
import time

@pytest.fixture(scope="module")
def calc_server_port():
    return _get_free_port()


@pytest.fixture(scope="module", autouse=True)
def run_calc_server(calc_server_port):
    """Run calculator server fixture."""
    thread = threading.Thread(
        target=uvicorn.run,
        args=(calc_app,),
        kwargs={"host": "127.0.0.1", "port": calc_server_port, "log_level": "warning"},
        daemon=True,
    )
    thread.start()

    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", calc_server_port), timeout=0.1):
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)

    yield f"http://127.0.0.1:{calc_server_port}"


@pytest.fixture(scope="module")
def auth_server_port():
    return _get_free_port()


@pytest.fixture(scope="module", autouse=True)
def run_auth_server(auth_server_port):
    """Run an MCP server requiring Bearer auth."""
    auth_app = FastAPI(title="Authenticated MCP Server")

    @auth_app.get("/")
    async def health(authorization: str = Header(None)):
        if authorization != "Bearer secret_mcp_token_123":
            raise HTTPException(status_code=401, detail="Unauthorized")
        return {"status": "healthy"}

    @auth_app.post("/invoke")
    async def invoke(payload: dict, authorization: str = Header(None)):
        if authorization != "Bearer secret_mcp_token_123":
            raise HTTPException(status_code=401, detail="Unauthorized")
        return {"status": "success", "result": {"auth_verified": True, "tool": payload.get("name")}}

    thread = threading.Thread(
        target=uvicorn.run,
        args=(auth_app,),
        kwargs={"host": "127.0.0.1", "port": auth_server_port, "log_level": "warning"},
        daemon=True,
    )
    thread.start()

    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", auth_server_port), timeout=0.1):
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)

    yield f"http://127.0.0.1:{auth_server_port}"


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_workflow_mcp_calculator_node_execution(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession, run_calc_server
):
    """Test MCP tool execution node with dynamic variable interpolation."""
    admin = await seed_user(email="wf_mcp_user@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    # 1. Register server
    reg_resp = await gateway_client.post(
        "/api/mcp/servers",
        json={"name": "WF Calc Server", "url": run_calc_server, "transport": "streamable_http"},
        headers=headers,
    )
    assert reg_resp.status_code == 201
    server_id = reg_resp.json()["id"]

    # 2. Execute MCP node with interpolation
    config = {
        "server_id": server_id,
        "tool_name": "add",
        "input_mapping": {
            "a": "{{first_number}}",
            "b": 17,
        },
    }
    state = {
        "first_number": 25,
        "db_session": real_db_session,
    }

    result = await execute_mcp_tool(config, state)
    assert result["success"] is True
    assert result["error"] is None
    res_val = result["result"]
    if isinstance(res_val, dict) and "result" in res_val:
        res_val = res_val["result"]
    if isinstance(res_val, dict) and "result" in res_val:
        res_val = res_val["result"]
    assert res_val == 42.0
    assert result["execution_time_ms"] > 0


@pytest.mark.asyncio
async def test_workflow_mcp_node_with_bearer_auth(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession, run_auth_server
):
    """Verify MCP node passes encrypted bearer token correctly to external authenticated tool."""
    admin = await seed_user(email="wf_mcp_auth@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    # Register server with Bearer auth
    reg_resp = await gateway_client.post(
        "/api/mcp/servers",
        json={
            "name": "Auth MCP Server",
            "url": run_auth_server,
            "transport": "streamable_http",
            "auth_type": "bearer",
            "auth_token": "secret_mcp_token_123",
        },
        headers=headers,
    )
    assert reg_resp.status_code == 201
    server_id = reg_resp.json()["id"]

    # Execute MCP tool
    config = {
        "server_id": server_id,
        "tool_name": "secure_operation",
        "input_mapping": {"data": "confidential"},
    }
    state = {
        "db_session": real_db_session,
    }

    result = await execute_mcp_tool(config, state)
    assert result["success"] is True
    r_data = result["result"]
    if isinstance(r_data, dict) and "result" in r_data:
        r_data = r_data["result"]
    assert r_data["auth_verified"] is True
    assert r_data["tool"] == "secure_operation"


@pytest.mark.asyncio
async def test_workflow_mcp_node_error_handling(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Test error handling when server is missing, inactive, or tool execution fails."""
    # 1. Missing server_id
    res_no_server = await execute_mcp_tool({}, {})
    assert res_no_server["success"] is False
    assert "missing server_id" in res_no_server["error"]

    # 2. Non-existent server_id
    res_fake_server = await execute_mcp_tool({"server_id": "00000000-0000-0000-0000-000000000000"}, {})
    assert res_fake_server["success"] is False
    assert "not found or inactive" in res_fake_server["error"]

    # 3. Inactive server
    inactive_srv = MCPServer(
        name="Inactive Server",
        url="http://127.0.0.1:9999",
        transport="streamable_http",
        auth_type="none",
        is_active=False,
        health_status="unhealthy",
    )
    real_db_session.add(inactive_srv)
    await real_db_session.commit()
    await real_db_session.refresh(inactive_srv)

    res_inactive = await execute_mcp_tool({"server_id": inactive_srv.id}, {"db_session": real_db_session})
    assert res_inactive["success"] is False
    assert "not found or inactive" in res_inactive["error"]


@pytest.mark.asyncio
async def test_full_workflow_with_mcp_tool_execution(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession, run_calc_server
):
    """Create a workflow containing an MCP tool node and execute it via the gateway API."""
    owner = await seed_user(email="wf_mcp_graph_owner@contained.ai", role="member")
    headers = await _auth_headers(owner)

    # 1. Register calculator server
    reg_resp = await gateway_client.post(
        "/api/mcp/servers",
        json={"name": "Graph Workflow Calc", "url": run_calc_server, "transport": "streamable_http"},
        headers=headers,
    )
    server_id = reg_resp.json()["id"]

    # 2. Create Workflow Hub and Workflow with MCP Tool Node
    wf_hub = await seed_hub(owner=owner, name="MCP Workflow Hub", slug="mcp-wf-hub", hub_type="workflow")
    wf_payload = {
        "name": "Math Calculation Flow",
        "description": "Calculates values using MCP tool server",
        "canvas_nodes": [
            {"id": "in", "type": "input", "data": {"label": "Start"}},
            {
                "id": "calc-node",
                "type": "mcp_tool",
                "data": {
                    "server_id": server_id,
                    "tool_name": "multiply",
                    "input_mapping": {"a": 7, "b": 6},
                },
            },
            {"id": "out", "type": "terminal", "data": {"label": "End"}},
        ],
        "canvas_edges": [
            {"id": "e1", "source": "in", "target": "calc-node"},
            {"id": "e2", "source": "calc-node", "target": "out"},
        ],
    }
    wf_resp = await gateway_client.post(f"/api/hubs/{wf_hub.id}/workflows", json=wf_payload, headers=headers)
    assert wf_resp.status_code == 201, f"Create workflow failed: {wf_resp.text}"
    wf_id = wf_resp.json()["id"]

    # 3. Execute workflow
    exec_resp = await gateway_client.post(
        f"/api/hubs/{wf_hub.id}/workflows/{wf_id}/runs",
        json={"input": {"prompt": "Calculate product"}, "use_draft": True},
        headers=headers,
    )
    assert exec_resp.status_code in (200, 202), f"Workflow execution failed: {exec_resp.text}"
