"""Tests for Tool Invocation API & Testing (S5-05c)."""

import pytest
from common.models.database import MCPServer
from gateway.services.mcp_client import invoke_tool


@pytest.mark.asyncio
async def test_tool_invocation_fallback():
    server = MCPServer(
        name="SyntraFlow (Internal)",
        url="http://localhost:8012",
        transport="sse",
        is_internal=True,
        is_active=True,
    )

    result = await invoke_tool(
        server=server,
        tool_name="execute_workflow_step",
        parameters={"node_id": "node_123", "input_data": {"test": "val"}},
    )

    assert result["status"] == "success"
    assert "execution_time_ms" in result
    assert result["execution_time_ms"] >= 0
