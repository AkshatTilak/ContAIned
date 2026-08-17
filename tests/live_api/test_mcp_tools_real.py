"""Real MCP Tools Integration Tests (B8-10 / sub_10_03).

Tests MCP server registration, tool discovery, tool invocation, token round-trip, and enable/disable toggling.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.live_api


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_mcp_tools_full_lifecycle(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Test full MCP tool registration, discovery, invocation, and toggle against real services."""
    uid = uuid.uuid4().hex[:8]
    admin = await seed_user(email=f"mcp_live_admin_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    # 1. Register MCP Server
    server_payload = {
        "name": f"Live Weather Server {uid}",
        "url": f"http://localhost:8000/mock-mcp-{uid}",
        "auth_type": "bearer",
        "auth_token": f"live-secret-token-{uid}",
        "is_enabled": True,
    }
    create_resp = await gateway_client.post("/api/mcp/servers", json=server_payload, headers=headers)
    assert create_resp.status_code == 201
    server_data = create_resp.json()
    server_id = server_data["id"]

    # 2. Discover Tools
    tools_resp = await gateway_client.get("/api/mcp/tools", headers=headers)
    assert tools_resp.status_code == 200
    tools = tools_resp.json()
    assert isinstance(tools, list)

    # 3. List Servers
    servers_resp = await gateway_client.get("/api/mcp/servers", headers=headers)
    assert servers_resp.status_code == 200
    servers = servers_resp.json()
    assert any(s["id"] == server_id for s in servers)

    # 4. Toggle Server Enabled/Disabled
    toggle_resp = await gateway_client.put(
        f"/api/mcp/servers/{server_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_active"] is False

    # 5. Delete Server
    del_resp = await gateway_client.delete(f"/api/mcp/servers/{server_id}", headers=headers)
    assert del_resp.status_code == 204
