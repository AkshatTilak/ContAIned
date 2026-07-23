"""Tests for Tool Discovery & Caching (S5-05b)."""

import pytest
from unittest.mock import AsyncMock
from common.models.database import MCPServer
from gateway.services.mcp_client import discover_tools


@pytest.mark.asyncio
async def test_tool_discovery_fallback():
    server = MCPServer(
        name="SyntraFlow (Internal)",
        url="http://localhost:8012",
        transport="sse",
        is_internal=True,
        is_active=True,
    )
    tools = await discover_tools(server)
    assert len(tools) >= 2
    tool_names = [t["tool_name"] for t in tools]
    assert "execute_workflow_step" in tool_names
    assert "query_vector_store" in tool_names
