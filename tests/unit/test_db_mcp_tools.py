
import pytest
pytestmark = pytest.mark.unit
"""Integration tests for the Database MCP Tool Bridge (Task 12_02).

Verifies:
1. generate_db_tool_definitions() produces the standard tool schemas.
2. execute_db_tool() dispatches db_schema_inspector / db_query_executor /
   mongo_collection_query to the correct connector.
3. Hub scoping is enforced (credential outside the hub is rejected).
4. format_rows_as_markdown() renders tabular SQL output for agent context.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from common.services.mcp_db_bridge import (
    generate_db_tool_definitions,
    execute_db_tool,
    format_rows_as_markdown,
)


class TestToolDefinitions:
    def test_postgres_credential_generates_schema_and_query_tools(self):
        cred = MagicMock()
        cred.db_type = "postgres"
        tools = generate_db_tool_definitions(cred)
        names = {t["tool_name"] for t in tools}
        assert "db_schema_inspector" in names
        assert "db_query_executor" in names
        assert "mongo_collection_query" not in names

    def test_mongo_credential_generates_mongo_tool(self):
        cred = MagicMock()
        cred.db_type = "mongodb"
        tools = generate_db_tool_definitions(cred)
        names = {t["tool_name"] for t in tools}
        assert "mongo_collection_query" in names

    def test_tool_schemas_have_required_fields(self):
        cred = MagicMock()
        cred.db_type = "postgres"
        tools = generate_db_tool_definitions(cred)
        for tool in tools:
            assert "tool_name" in tool
            assert "description" in tool
            assert "input_schema_json" in tool
            assert "credential_id" in tool["input_schema_json"]["properties"]


class TestExecuteDbTool:
    @pytest.mark.asyncio
    async def test_schema_inspector_returns_metadata(self):
        mock_cred = MagicMock()
        mock_cred.id = "cred-1"
        mock_cred.hub_id = "hub-1"
        mock_cred.db_type = "postgres"
        mock_cred.encrypted_secret_payload = None

        mock_connector = AsyncMock()
        mock_connector.get_schema_metadata = AsyncMock(
            return_value={"tables": ["users", "orders"]}
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_cred)
        mock_session_factory = MagicMock(return_value=mock_session)

        with (
            patch(
                "common.services.mcp_db_bridge.get_sessionmaker",
                return_value=mock_session_factory,
            ),
            patch(
                "common.services.mcp_db_bridge.get_connector",
                new_callable=AsyncMock,
                return_value=mock_connector,
            ),
        ):
            result = await execute_db_tool(
                "db_schema_inspector",
                {"credential_id": "cred-1"},
                hub_id="hub-1",
            )

        assert result["status"] == "success"
        assert result["result"]["tables"] == ["users", "orders"]

    @pytest.mark.asyncio
    async def test_query_executor_returns_rows(self):
        mock_cred = MagicMock()
        mock_cred.id = "cred-1"
        mock_cred.hub_id = "hub-1"
        mock_cred.db_type = "postgres"
        mock_cred.encrypted_secret_payload = None

        mock_connector = AsyncMock()
        mock_connector.execute_query = AsyncMock(
            return_value=[{"id": 1, "name": "Akshat"}]
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_cred)
        mock_session_factory = MagicMock(return_value=mock_session)

        with (
            patch(
                "common.services.mcp_db_bridge.get_sessionmaker",
                return_value=mock_session_factory,
            ),
            patch(
                "common.services.mcp_db_bridge.get_connector",
                new_callable=AsyncMock,
                return_value=mock_connector,
            ),
        ):
            result = await execute_db_tool(
                "db_query_executor",
                {"credential_id": "cred-1", "sql_query": "SELECT * FROM users"},
                hub_id="hub-1",
            )

        assert result["status"] == "success"
        assert result["result"][0]["name"] == "Akshat"
        mock_connector.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_hub_scoping_rejects_foreign_credential(self):
        """A credential in a different hub is rejected."""
        mock_cred = MagicMock()
        mock_cred.id = "cred-1"
        mock_cred.hub_id = "hub-OTHER"
        mock_cred.db_type = "postgres"
        mock_cred.encrypted_secret_payload = None

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_cred)
        mock_session_factory = MagicMock(return_value=mock_session)

        with patch(
            "common.services.mcp_db_bridge.get_sessionmaker",
            return_value=mock_session_factory,
        ):
            result = await execute_db_tool(
                "db_schema_inspector",
                {"credential_id": "cred-1"},
                hub_id="hub-1",
            )

        assert result["status"] == "error"
        assert "not accessible" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_credential_id_returns_error(self):
        result = await execute_db_tool("db_schema_inspector", {})
        assert result["status"] == "error"
        assert "credential_id" in result["error"]


class TestFormatRowsAsMarkdown:
    def test_formats_rows_as_table(self):
        rows = [{"id": 1, "name": "Akshat"}, {"id": 2, "name": "Bob"}]
        md = format_rows_as_markdown(rows)
        assert "| id | name |" in md
        assert "| 1 | Akshat |" in md
        assert "| 2 | Bob |" in md

    def test_empty_rows(self):
        assert format_rows_as_markdown([]) == "_No rows returned._"
