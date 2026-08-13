
import pytest
pytestmark = pytest.mark.unit
"""Unit tests for DatabaseQueryNode / DBStoreNode executors (Task 12_03).

Verifies:
1. Parametrized SQL query resolution from state / params_mapping.
2. execute_database_query_node resolves a hub-scoped ExternalCredential and
   executes a read-only query via the connector pool.
3. execute_db_store_node performs insert/upsert against a connector.
4. Missing credential / read-only enforcement surfaces errors.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict

from projects.guardroute.src.nodes.db_query_executor import (
    _extract_params,
    _resolve_param_value,
    execute_database_query_node,
)
from projects.guardroute.src.nodes.db_store_executor import execute_db_store_node


# ---------------------------------------------------------------------------
# Param extraction / resolution helpers
# ---------------------------------------------------------------------------

class TestParamHelpers:
    def test_extract_params_finds_named_placeholders(self):
        sql = "SELECT * FROM users WHERE user_id = :user_id AND status = :status"
        assert set(_extract_params(sql)) == {"user_id", "status"}

    def test_extract_params_ignores_double_colon_cast(self):
        sql = "SELECT id::text FROM t WHERE x = :x"
        assert _extract_params(sql) == ["x"]

    def test_resolve_param_from_mapping(self):
        state = {"input": {"user_id": 123}}
        mapping = {"user_id": "{{input.user_id}}"}
        assert _resolve_param_value("user_id", state, mapping) == "123"

    def test_resolve_param_from_state_fallback(self):
        state = {"status": "active"}
        assert _resolve_param_value("status", state, {}) == "active"


# ---------------------------------------------------------------------------
# execute_database_query_node
# ---------------------------------------------------------------------------

class TestDatabaseQueryNode:
    @pytest.mark.asyncio
    async def test_executes_query_and_returns_rows(self):
        """A valid credential + query returns rows and row_count."""
        mock_cred = MagicMock()
        mock_cred.id = "cred-1"
        mock_cred.hub_id = "hub-1"
        mock_cred.db_type = "postgres"
        mock_cred.encrypted_secret_payload = None

        mock_connector = AsyncMock()
        mock_connector.execute_query = AsyncMock(
            return_value=[{"id": 1, "name": "Akshat"}, {"id": 2, "name": "Bob"}]
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_cred)
        mock_session_factory = MagicMock(return_value=mock_session)

        config = {
            "credential_id": "cred-1",
            "query_template": "SELECT * FROM users WHERE user_id = :user_id",
            "params_mapping": {"user_id": "{{input.user_id}}"},
            "timeout_s": 30,
            "max_rows": 500,
        }
        state = {"hub_id": "hub-1", "input": {"user_id": 123}}

        with (
            patch(
                "projects.guardroute.src.nodes.db_query_executor.get_sessionmaker",
                return_value=mock_session_factory,
            ),
            patch(
                "projects.guardroute.src.nodes.db_query_executor.get_connector",
                new_callable=AsyncMock,
                return_value=mock_connector,
            ),
        ):
            result = await execute_database_query_node(config, state)

        assert result["success"] is True
        assert result["row_count"] == 2
        assert result["rows"][0]["name"] == "Akshat"
        # Verify the connector was called with the parametrized query
        mock_connector.execute_query.assert_called_once()
        call_kwargs = mock_connector.execute_query.call_args
        assert call_kwargs[0][0] == "SELECT * FROM users WHERE user_id = :user_id"

    @pytest.mark.asyncio
    async def test_missing_credential_returns_error(self):
        """A missing credential_id returns a graceful error (routes to error handle)."""
        config = {"credential_id": "", "query_template": "SELECT 1"}
        result = await execute_database_query_node(config, {"hub_id": "hub-1"})
        assert result["success"] is False
        assert "credential_id" in result["error"]

    @pytest.mark.asyncio
    async def test_credential_not_found_in_hub_returns_error(self):
        """A credential not found in the hub returns an error."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
        mock_session_factory = MagicMock(return_value=mock_session)

        config = {
            "credential_id": "cred-missing",
            "query_template": "SELECT 1",
        }
        state = {"hub_id": "hub-1"}

        with patch(
            "projects.guardroute.src.nodes.db_query_executor.get_sessionmaker",
            return_value=mock_session_factory,
        ):
            result = await execute_database_query_node(config, state)

        assert result["success"] is False
        assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# execute_db_store_node
# ---------------------------------------------------------------------------

class TestDBStoreNode:
    @pytest.mark.asyncio
    async def test_insert_record(self):
        """DBStoreNode inserts a record and returns affected count."""
        mock_cred = MagicMock()
        mock_cred.id = "cred-1"
        mock_cred.hub_id = "hub-1"
        mock_cred.db_type = "postgres"
        mock_cred.encrypted_secret_payload = None

        mock_connector = AsyncMock()
        mock_connector.store_record = AsyncMock(return_value={"affected": 1, "primary_key": 42})

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_cred)
        mock_session_factory = MagicMock(return_value=mock_session)

        config = {
            "credential_id": "cred-1",
            "target_table": "users",
            "operation": "insert",
            "record_mapping": {"name": "{{input.name}}", "role": "{{input.role}}"},
        }
        state = {"hub_id": "hub-1", "input": {"name": "Akshat", "role": "engineer"}}

        with (
            patch(
                "projects.guardroute.src.nodes.db_store_executor.get_sessionmaker",
                return_value=mock_session_factory,
            ),
            patch(
                "projects.guardroute.src.nodes.db_store_executor.get_connector",
                new_callable=AsyncMock,
                return_value=mock_connector,
            ),
        ):
            result = await execute_db_store_node(config, state)

        assert result["success"] is True
        assert result["affected"] == 1
        assert result["primary_key"] == 42
        # Verify the record was interpolated from state
        store_call = mock_connector.store_record.call_args
        assert store_call.kwargs["record"] == {"name": "Akshat", "role": "engineer"}
        assert store_call.kwargs["operation"] == "insert"

    @pytest.mark.asyncio
    async def test_read_only_credential_refuses_write(self):
        """A read-only credential refuses a DBStoreNode write."""
        mock_cred = MagicMock()
        mock_cred.id = "cred-1"
        mock_cred.hub_id = "hub-1"
        mock_cred.db_type = "postgres"
        mock_cred.encrypted_secret_payload = None

        mock_connector = AsyncMock()
        mock_connector.store_record = AsyncMock(
            side_effect=ValueError("DBStoreNode write refused: credential is read-only.")
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_cred)
        mock_session_factory = MagicMock(return_value=mock_session)

        config = {
            "credential_id": "cred-1",
            "target_table": "users",
            "operation": "insert",
            "record_mapping": {"name": "x"},
        }
        state = {"hub_id": "hub-1"}

        with (
            patch(
                "projects.guardroute.src.nodes.db_store_executor.get_sessionmaker",
                return_value=mock_session_factory,
            ),
            patch(
                "projects.guardroute.src.nodes.db_store_executor.get_connector",
                new_callable=AsyncMock,
                return_value=mock_connector,
            ),
        ):
            result = await execute_db_store_node(config, state)

        assert result["success"] is False
        assert "read-only" in result["error"]
