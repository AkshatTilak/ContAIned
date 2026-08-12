"""Async MySQL connector using aiomysql (Task 12).

Read-only transactions are enforced via `SET SESSION TRANSACTION READ ONLY`.
Statement timeout via `MAX_STATEMENT_TIME` (MySQL 5.7.8+) or advisory timeout.
"""

import logging
from typing import Any, Dict, List, Optional

from common.clients.db_connectors.base import BaseDatabaseConnector

logger = logging.getLogger("common.clients.db_connectors.mysql")


class MySQLConnector(BaseDatabaseConnector):
    """Async MySQL connector backed by aiomysql."""

    def __init__(self, credential_id: str, config: Dict[str, Any]) -> None:
        super().__init__(credential_id, config)
        self._pool: Any = None

    async def connect(self) -> None:
        try:
            import aiomysql  # type: ignore
        except ImportError as exc:
            raise ImportError("aiomysql is required for MySQLConnector. Install with: pip install aiomysql") from exc

        cfg = self.config
        self._pool = await aiomysql.create_pool(
            host=cfg.get("host", "localhost"),
            port=int(cfg.get("port", 3306)),
            user=cfg.get("username", "root"),
            password=cfg.get("password", ""),
            db=cfg.get("database_name", ""),
            maxsize=cfg.get("max_connections", 10),
            autocommit=True,
            connect_timeout=10,
        )
        self._connected = True
        logger.info("MySQLConnector[%s] pool opened", self.credential_id)

    async def close(self) -> None:
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            self._connected = False

    async def test_connection(self) -> bool:
        if not self._pool:
            await self.connect()
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
            return True
        except Exception as exc:
            logger.warning("MySQLConnector[%s] ping failed: %s", self.credential_id, exc)
            return False

    async def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_s: int = BaseDatabaseConnector.DEFAULT_TIMEOUT_S,
        max_rows: int = BaseDatabaseConnector.MAX_ROWS,
    ) -> List[Dict[str, Any]]:
        self._assert_safe(query)
        if not self._pool:
            await self.connect()

        timeout_ms = int(timeout_s * 1000)
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                if self.is_read_only:
                    await cur.execute("SET SESSION TRANSACTION READ ONLY")
                await cur.execute(f"SET SESSION MAX_STATEMENT_TIME = {timeout_ms}")

                # Convert :name → %(name)s for aiomysql
                mysql_query = self._to_pyformat(query)
                await cur.execute(mysql_query, params or {})
                columns = [d[0] for d in (cur.description or [])]
                fetched = await cur.fetchmany(min(max_rows, self.MAX_ROWS))
                rows = [dict(zip(columns, row)) for row in fetched]
        return rows

    async def get_schema_metadata(self) -> Dict[str, Any]:
        if not self._pool:
            await self.connect()
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES")
                tables = [row[0] for row in await cur.fetchall()]
        return {"tables": tables}

    async def store_record(
        self,
        target_table: str,
        record: Dict[str, Any],
        operation: str = "insert",
    ) -> Dict[str, Any]:
        """Insert/upsert a record into a MySQL table."""
        if self.is_read_only:
            raise ValueError("DBStoreNode write refused: credential is read-only.")
        if not self._pool:
            await self.connect()

        if not record:
            return {"affected": 0, "primary_key": None}

        columns = list(record.keys())
        col_sql = ", ".join(f"`{c}`" for c in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        values = [record[c] for c in columns]

        if operation == "upsert":
            update_set = ", ".join(f"`{c}` = VALUES(`{c}`)" for c in columns)
            sql = (
                f"INSERT INTO `{target_table}` ({col_sql}) VALUES ({placeholders}) "
                f"ON DUPLICATE KEY UPDATE {update_set}"
            )
        else:  # insert / append
            sql = f"INSERT INTO `{target_table}` ({col_sql}) VALUES ({placeholders})"

        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, values)
                affected = cur.rowcount
                last_id = cur.lastrowid
        return {"affected": affected, "primary_key": last_id}

    @staticmethod
    def _to_pyformat(query: str) -> str:
        import re
        return re.sub(r":([a-zA-Z_]\w*)", r"%(\1)s", query)
