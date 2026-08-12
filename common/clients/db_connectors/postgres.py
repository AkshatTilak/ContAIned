"""Async PostgreSQL connector using asyncpg (Task 12).

Read-only transactions are enforced via `SET TRANSACTION READ ONLY` when
`is_read_only=True`. Statement timeouts are applied via `SET statement_timeout`.
"""

import logging
from typing import Any, Dict, List, Optional

from common.clients.db_connectors.base import BaseDatabaseConnector

logger = logging.getLogger("common.clients.db_connectors.postgres")


class PostgresConnector(BaseDatabaseConnector):
    """Async PostgreSQL connector backed by asyncpg.

    asyncpg is used directly instead of SQLAlchemy for full async support and
    low-overhead connection pooling. Falls back to a graceful error if asyncpg
    is not installed.
    """

    def __init__(self, credential_id: str, config: Dict[str, Any]) -> None:
        super().__init__(credential_id, config)
        self._pool: Any = None

    async def connect(self) -> None:
        try:
            import asyncpg  # type: ignore
        except ImportError as exc:
            raise ImportError("asyncpg is required for PostgresConnector. Install with: pip install asyncpg") from exc

        dsn = self._build_dsn()
        timeout = self.config.get("statement_timeout_ms", 30_000) / 1000.0

        self._pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=self.config.get("max_connections", 10),
            command_timeout=timeout,
        )
        self._connected = True
        logger.info("PostgresConnector[%s] pool opened", self.credential_id)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._connected = False

    async def test_connection(self) -> bool:
        if not self._pool:
            await self.connect()
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as exc:
            logger.warning("PostgresConnector[%s] ping failed: %s", self.credential_id, exc)
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

        timeout = float(timeout_s)
        async with self._pool.acquire() as conn:
            await conn.execute(f"SET statement_timeout = {int(timeout * 1000)}")
            if self.is_read_only:
                await conn.execute("SET TRANSACTION READ ONLY")

            # Convert named :param placeholders to asyncpg positional $1 style
            args, pg_query = self._convert_params(query, params or {})
            records = await conn.fetch(pg_query, *args, timeout=timeout)

        rows = [dict(r) for r in records]
        return self._cap_rows(rows, max_rows)

    async def get_schema_metadata(self) -> Dict[str, Any]:
        if not self._pool:
            await self.connect()
        async with self._pool.acquire() as conn:
            tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
        return {"tables": [r["table_name"] for r in tables]}

    async def store_record(
        self,
        target_table: str,
        record: Dict[str, Any],
        operation: str = "insert",
    ) -> Dict[str, Any]:
        """Insert/upsert a record into a Postgres table."""
        if self.is_read_only:
            raise ValueError("DBStoreNode write refused: credential is read-only.")
        if not self._pool:
            await self.connect()

        if not record:
            return {"affected": 0, "primary_key": None}

        columns = list(record.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
        col_sql = ", ".join(f'"{c}"' for c in columns)
        values = [record[c] for c in columns]

        if operation == "upsert":
            # Simple upsert: ON CONFLICT DO UPDATE on all non-key columns.
            update_set = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in columns)
            sql = (
                f'INSERT INTO "{target_table}" ({col_sql}) VALUES ({placeholders}) '
                f'ON CONFLICT DO UPDATE SET {update_set} RETURNING *'
            )
        else:  # insert / append
            sql = f'INSERT INTO "{target_table}" ({col_sql}) VALUES ({placeholders}) RETURNING *'

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, *values)
        return {"affected": 1, "primary_key": dict(row) if row else None}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_dsn(self) -> str:
        cfg = self.config
        host = cfg.get("host", "localhost")
        port = cfg.get("port", 5432)
        db = cfg.get("database_name", "postgres")
        user = cfg.get("username", "postgres")
        pwd = cfg.get("password", "")
        return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

    @staticmethod
    def _convert_params(query: str, params: Dict[str, Any]):
        """Convert :name params to asyncpg $N positional style."""
        import re
        args: List[Any] = []
        counter = [0]

        def replacer(m: re.Match) -> str:
            name = m.group(1)
            args.append(params.get(name))
            counter[0] += 1
            return f"${counter[0]}"

        pg_query = re.sub(r":([a-zA-Z_]\w*)", replacer, query)
        return args, pg_query
