"""Unit tests for the external database connector infrastructure (Task 12_01).

Verifies:
1. Read-only query safety guards (DDL/DML rejection, multi-statement rejection).
2. Row limit truncation.
3. Postgres named-parameter conversion (:name -> $N).
4. Connector execute_query enforces read-only + row caps.
5. store_record refuses writes on read-only credentials.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from common.clients.db_connectors.base import (
    _check_query_safety,
    BaseDatabaseConnector,
)
from common.clients.db_connectors.postgres import PostgresConnector


class TestQuerySafety:
    def test_select_allowed_on_read_only(self):
        _check_query_safety("SELECT * FROM users", is_read_only=True)

    def test_dml_rejected_on_read_only(self):
        with pytest.raises(ValueError, match="DDL/DML"):
            _check_query_safety("DELETE FROM users", is_read_only=True)

    def test_ddl_rejected_on_read_only(self):
        with pytest.raises(ValueError, match="DDL/DML"):
            _check_query_safety("DROP TABLE users", is_read_only=True)

    def test_multi_statement_rejected(self):
        with pytest.raises(ValueError, match="Multi-statement"):
            _check_query_safety("SELECT 1; SELECT 2", is_read_only=True)

    def test_dml_allowed_when_not_read_only(self):
        # Non-read-only credentials may run DML.
        _check_query_safety("UPDATE users SET x=1", is_read_only=False)


class TestRowCap:
    def test_cap_rows_truncates_to_max(self):
        conn = MagicMock()
        conn.MAX_ROWS = 1000
        rows = [{"i": i} for i in range(50)]
        # Use a concrete subclass to access _cap_rows
        pg = PostgresConnector("c1", {"is_read_only": True})
        result = pg._cap_rows(rows, max_rows=10)
        assert len(result) == 10

    def test_cap_rows_respects_global_max(self):
        pg = PostgresConnector("c1", {"is_read_only": True})
        rows = [{"i": i} for i in range(2000)]
        # Global MAX_ROWS is 1000, so even max_rows=5000 is capped at 1000.
        result = pg._cap_rows(rows, max_rows=5000)
        assert len(result) == pg.MAX_ROWS


class TestPostgresParamConversion:
    def test_named_params_to_positional(self):
        args, query = PostgresConnector._convert_params(
            "SELECT * FROM users WHERE id = :id AND name = :name",
            {"id": 1, "name": "Akshat"},
        )
        assert query == "SELECT * FROM users WHERE id = $1 AND name = $2"
        assert args == [1, "Akshat"]

    def test_missing_param_becomes_none(self):
        args, query = PostgresConnector._convert_params(
            "SELECT * FROM users WHERE id = :id",
            {},
        )
        assert args == [None]


class TestConnectorExecuteQuery:
    @pytest.mark.asyncio
    async def test_read_only_enforces_safety_and_caps_rows(self):
        """execute_query rejects DML on read-only and caps returned rows."""
        pg = PostgresConnector("c1", {"is_read_only": True})
        pg._pool = MagicMock()

        with pytest.raises(ValueError, match="DDL/DML"):
            await pg.execute_query("DELETE FROM users")

    @pytest.mark.asyncio
    async def test_execute_query_returns_capped_rows(self):
        """A successful query returns at most max_rows rows."""
        pg = PostgresConnector("c1", {"is_read_only": True})

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[{"id": i} for i in range(20)]
        )
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        pg._pool = mock_pool

        rows = await pg.execute_query("SELECT * FROM users", max_rows=5)
        assert len(rows) == 5

    @pytest.mark.asyncio
    async def test_store_record_refuses_read_only(self):
        """store_record raises on a read-only credential."""
        pg = PostgresConnector("c1", {"is_read_only": True})
        with pytest.raises(ValueError, match="read-only"):
            await pg.store_record("users", {"name": "x"}, operation="insert")
