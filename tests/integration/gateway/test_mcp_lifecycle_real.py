"""Real-world integration test suite for MCP Registry Lifecycle against live Gateway and Postgres.

Tests server registration, health checks, tool auto-discovery, invocation (REST/JSON-RPC),
tool enabling/disabling, metadata updates, cascading deletion, and internal server guards.
"""

import asyncio
import socket
import pytest
import uvicorn
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import MCPServer, MCPToolCache
from gateway.auth.utils import create_access_token
from mcp_tools.sample_calculator.server import app as calc_app

pytestmark = pytest.mark.integration


def _get_free_port() -> int:
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


import threading
import time

@pytest.fixture(scope="module")
def sample_calculator_port():
    """Returns a free port for the test calculator server."""
    return _get_free_port()


@pytest.fixture(scope="module", autouse=True)
def run_sample_calculator_server(sample_calculator_port):
    """Run sample calculator server in a background daemon thread."""
    thread = threading.Thread(
        target=uvicorn.run,
        args=(calc_app,),
        kwargs={"host": "127.0.0.1", "port": sample_calculator_port, "log_level": "warning"},
        daemon=True,
    )
    thread.start()

    # Wait until server is listening
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", sample_calculator_port), timeout=0.1):
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)

    yield f"http://127.0.0.1:{sample_calculator_port}"


async def _auth_headers(user) -> dict:
    """Build Authorization header for a seeded user."""
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_mcp_server_registration_and_health(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession, run_sample_calculator_server
):
    """Test registering the sample calculator MCP server and verifying health status."""
    admin = await seed_user(email="mcp_admin@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    server_url = run_sample_calculator_server
    payload = {
        "name": "Sample Calculator Live",
        "url": server_url,
        "transport": "streamable_http",
        "auth_type": "none",
    }

    # 1. Register Server
    resp = await gateway_client.post("/api/mcp/servers", json=payload, headers=headers)
    assert resp.status_code == 201, f"Register MCP server failed: {resp.text}"
    data = resp.json()
    assert data["name"] == "Sample Calculator Live"
    assert data["url"] == server_url
    assert data["health_status"] == "healthy"
    assert data["tool_count"] >= 5
    server_id = data["id"]

    # 2. Verify DB state
    db_server = (await real_db_session.execute(select(MCPServer).where(MCPServer.id == server_id))).scalar_one_or_none()
    assert db_server is not None
    assert db_server.name == "Sample Calculator Live"
    assert db_server.health_status == "healthy"

    # 3. Trigger manual health check
    health_resp = await gateway_client.post(f"/api/mcp/servers/{server_id}/health", headers=headers)
    assert health_resp.status_code == 200
    assert health_resp.json()["health_status"] == "healthy"


@pytest.mark.asyncio
async def test_mcp_tool_discovery_and_invocation(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession, run_sample_calculator_server
):
    """Verify tool discovery, caching, and execution through gateway invocation endpoints."""
    admin = await seed_user(email="mcp_invoker@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    server_url = run_sample_calculator_server
    reg_resp = await gateway_client.post(
        "/api/mcp/servers",
        json={"name": "Invoker Calculator", "url": server_url, "transport": "streamable_http"},
        headers=headers,
    )
    server_id = reg_resp.json()["id"]

    # 1. Discover tools
    tools_resp = await gateway_client.get(f"/api/mcp/servers/{server_id}/tools", headers=headers)
    assert tools_resp.status_code == 200
    tools = tools_resp.json()
    tool_names = {t["tool_name"] for t in tools}
    assert "add" in tool_names
    assert "subtract" in tool_names
    assert "multiply" in tool_names
    assert "divide" in tool_names
    assert "power" in tool_names

    # 2. Invoke 'add' tool via REST /invoke
    invoke_resp = await gateway_client.post(
        "/api/mcp/tools/invoke",
        json={"server_id": server_id, "tool_name": "add", "parameters": {"a": 15, "b": 27}},
        headers=headers,
    )
    assert invoke_resp.status_code == 200
    inv_data = invoke_resp.json()
    assert inv_data["status"] == "success"
    res_val = inv_data["result"]
    if isinstance(res_val, dict) and "result" in res_val:
        res_val = res_val["result"]
    if isinstance(res_val, dict) and "result" in res_val:
        res_val = res_val["result"]
    assert res_val == 42.0

    # 3. Invoke 'multiply' tool
    mult_resp = await gateway_client.post(
        "/api/mcp/tools/invoke",
        json={"server_id": server_id, "tool_name": "multiply", "parameters": {"a": 6, "b": 7}},
        headers=headers,
    )
    assert mult_resp.status_code == 200
    m_val = mult_resp.json()["result"]
    if isinstance(m_val, dict) and "result" in m_val:
        m_val = m_val["result"]
    if isinstance(m_val, dict) and "result" in m_val:
        m_val = m_val["result"]
    assert m_val == 42.0

    # 4. Inline test endpoint
    test_resp = await gateway_client.post(
        f"/api/mcp/servers/{server_id}/tools/power/test",
        json={"parameters": {"base": 2, "exponent": 8}},
        headers=headers,
    )
    assert test_resp.status_code == 200
    p_val = test_resp.json()["result"]
    if isinstance(p_val, dict) and "result" in p_val:
        p_val = p_val["result"]
    if isinstance(p_val, dict) and "result" in p_val:
        p_val = p_val["result"]
    assert p_val == 256.0


@pytest.mark.asyncio
async def test_mcp_tool_toggle_and_aggregate_listing(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession, run_sample_calculator_server
):
    """Test enabling/disabling tools and aggregate tool listing."""
    admin = await seed_user(email="mcp_toggler@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    server_url = run_sample_calculator_server
    reg_resp = await gateway_client.post(
        "/api/mcp/servers",
        json={"name": "Toggle Test Server", "url": server_url, "transport": "streamable_http"},
        headers=headers,
    )
    server_id = reg_resp.json()["id"]

    # 1. Get cached tools
    tools_resp = await gateway_client.get(f"/api/mcp/servers/{server_id}/tools", headers=headers)
    tools = tools_resp.json()
    add_tool = next(t for t in tools if t["tool_name"] == "add")
    tool_id = add_tool["id"]

    # 2. Toggle tool off
    toggle_resp = await gateway_client.put(f"/api/mcp/tools/{tool_id}/toggle", headers=headers)
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_enabled"] is False

    # 3. Verify in DB
    tool_row = (await real_db_session.execute(select(MCPToolCache).where(MCPToolCache.id == tool_id))).scalar_one()
    assert tool_row.is_enabled is False

    # 4. Toggle tool back on
    toggle_on = await gateway_client.put(f"/api/mcp/tools/{tool_id}/toggle", headers=headers)
    assert toggle_on.status_code == 200
    assert toggle_on.json()["is_enabled"] is True

    # 5. List all tools across all active servers
    all_tools_resp = await gateway_client.get("/api/mcp/tools", headers=headers)
    assert all_tools_resp.status_code == 200
    all_tools = all_tools_resp.json()
    assert len(all_tools) >= 5


@pytest.mark.asyncio
async def test_mcp_server_update_delete_and_internal_guard(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession, run_sample_calculator_server
):
    """Test updating server details, deleting external servers, and preventing internal server deletion."""
    admin = await seed_user(email="mcp_updater@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    server_url = run_sample_calculator_server
    reg_resp = await gateway_client.post(
        "/api/mcp/servers",
        json={"name": "Server To Update", "url": server_url, "transport": "streamable_http"},
        headers=headers,
    )
    server_id = reg_resp.json()["id"]

    # 1. Update server name
    upd_resp = await gateway_client.put(
        f"/api/mcp/servers/{server_id}",
        json={"name": "Server Renamed Successfully"},
        headers=headers,
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["name"] == "Server Renamed Successfully"

    # 2. Delete server -> 204
    del_resp = await gateway_client.delete(f"/api/mcp/servers/{server_id}", headers=headers)
    assert del_resp.status_code == 204

    # Verify server is deleted from DB
    deleted_row = (await real_db_session.execute(select(MCPServer).where(MCPServer.id == server_id))).scalar_one_or_none()
    assert deleted_row is None

    # 3. Test internal server guard: create internal server in DB
    internal_server = MCPServer(
        name="System Internal MCP",
        url="http://internal-system:9000",
        transport="streamable_http",
        auth_type="none",
        is_internal=True,
        is_active=True,
        health_status="healthy",
    )
    real_db_session.add(internal_server)
    await real_db_session.commit()
    await real_db_session.refresh(internal_server)

    # Attempt deletion of internal server -> 400 Bad Request
    del_internal_resp = await gateway_client.delete(f"/api/mcp/servers/{internal_server.id}", headers=headers)
    assert del_internal_resp.status_code == 400
    assert "Cannot delete internal system MCP server" in del_internal_resp.text
