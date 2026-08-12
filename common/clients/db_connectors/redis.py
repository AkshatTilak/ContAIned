"""Async Redis connector using redis.asyncio (Task 12).

Read-only enforcement: commands like `SET`, `DEL`, `FLUSHDB`, `FLUSHALL`, `EXPIRE`
are blocked when `is_read_only=True`. Commands like `GET`, `HGETALL`, `LRANGE`, `KEYS`
are allowed.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from common.clients.db_connectors.base import BaseDatabaseConnector

logger = logging.getLogger("common.clients.db_connectors.redis")

_REDIS_WRITE_COMMANDS = {
    "SET", "SETNX", "MSET", "DEL", "UNLINK", "EXPIRE", "PEXPIRE", "PERSIST",
    "HSET", "HDEL", "HMSET", "LPUSH", "RPUSH", "LPOP", "RPOP", "SADD", "SREM",
    "ZADD", "ZREM", "FLUSHDB", "FLUSHALL", "EVAL", "EVALSHA", "SCRIPT"
}


class RedisConnector(BaseDatabaseConnector):
    """Async Redis connector backed by redis.asyncio."""

    def __init__(self, credential_id: str, config: Dict[str, Any]) -> None:
        super().__init__(credential_id, config)
        self._client: Any = None

    async def connect(self) -> None:
        try:
            import redis.asyncio as redis  # type: ignore
        except ImportError as exc:
            raise ImportError("redis is required for RedisConnector. Install with: pip install redis") from exc

        cfg = self.config
        host = cfg.get("host", "localhost")
        port = int(cfg.get("port", 6379))
        db = int(cfg.get("database_name") or 0)
        password = cfg.get("password") or None
        username = cfg.get("username") or None
        timeout_s = float(cfg.get("statement_timeout_ms", 30_000)) / 1000.0

        self._client = redis.Redis(
            host=host,
            port=port,
            db=db,
            username=username,
            password=password,
            socket_timeout=timeout_s,
            socket_connect_timeout=10.0,
            decode_responses=True,
        )
        self._connected = True
        logger.info("RedisConnector[%s] client created", self.credential_id)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            self._connected = False

    async def test_connection(self) -> bool:
        if not self._client:
            await self.connect()
        try:
            res = await self._client.ping()
            return bool(res)
        except Exception as exc:
            logger.warning("RedisConnector[%s] ping failed: %s", self.credential_id, exc)
            return False

    async def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_s: int = BaseDatabaseConnector.DEFAULT_TIMEOUT_S,
        max_rows: int = BaseDatabaseConnector.MAX_ROWS,
    ) -> List[Dict[str, Any]]:
        """Execute a Redis command.

        `query` is a Redis command string, e.g. "GET user:100" or "KEYS cache:*".
        `params` can optionally pass arguments if `query` is just the command name.
        """
        if not self._client:
            await self.connect()

        parts = query.strip().split()
        if not parts:
            return []

        cmd = parts[0].upper()

        if self.is_read_only and cmd in _REDIS_WRITE_COMMANDS:
            raise ValueError(f"Redis command '{cmd}' is prohibited on read-only credentials.")

        args = parts[1:]
        if params and "args" in params:
            args.extend([str(a) for a in params["args"]])

        try:
            raw_res = await self._client.execute_command(cmd, *args)
        except Exception as exc:
            logger.exception("Redis command '%s' failed", cmd)
            raise RuntimeError(f"Redis command execution failed: {exc}") from exc

        # Format result into standard dict array shape
        if isinstance(raw_res, list):
            rows = [{"index": i, "value": v} for i, v in enumerate(raw_res)]
        elif isinstance(raw_res, dict):
            rows = [{"key": k, "value": v} for k, v in raw_res.items()]
        else:
            rows = [{"command": cmd, "result": raw_res}]

        return self._cap_rows(rows, max_rows)

    async def get_schema_metadata(self) -> Dict[str, Any]:
        if not self._client:
            await self.connect()
        try:
            info = await self._client.info("keyspace")
            dbs = list(info.keys())
            return {"dbs": dbs, "info": info}
        except Exception:
            return {"dbs": ["db0"]}
