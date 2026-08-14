"""Connector Pool Manager for caching and retrieving database connectors by credential_id (Task 12).

Maintains a thread-safe / async-safe dictionary of active `BaseDatabaseConnector`
instances per `credential_id`.
"""

import asyncio
import logging
from typing import Dict, Optional, Any

from common.clients.db_connectors.base import BaseDatabaseConnector
from common.clients.db_connectors.postgres import PostgresConnector
from common.clients.db_connectors.mysql import MySQLConnector
from common.clients.db_connectors.mongo import MongoConnector
from common.clients.db_connectors.redis import RedisConnector
from common.security.crypto import decrypt_credential_payload, SecretDecryptionError

logger = logging.getLogger("common.clients.db_connectors.pool_manager")

DRIVER_MAP = {
    "postgres": PostgresConnector,
    "postgresql": PostgresConnector,
    "mysql": MySQLConnector,
    "mongodb": MongoConnector,
    "mongo": MongoConnector,
    "redis": RedisConnector,
}


class ConnectorPoolManager:
    """Manages lifecycle and connection pools for external database credentials."""

    _instance: Optional["ConnectorPoolManager"] = None

    def __init__(self) -> None:
        self._connectors: Dict[str, BaseDatabaseConnector] = {}
        self._lock_obj: Optional[asyncio.Lock] = None

    @property
    def _lock(self) -> asyncio.Lock:
        if self._lock_obj is None:
            self._lock_obj = asyncio.Lock()
        return self._lock_obj

    @classmethod
    def get_instance(cls) -> "ConnectorPoolManager":
        if cls._instance is None:
            cls._instance = ConnectorPoolManager()
        return cls._instance

    async def get_connector(
        self,
        credential_row: Any,
    ) -> BaseDatabaseConnector:
        """Fetch an existing active connector or instantiate & connect a new one."""
        cid = str(credential_row.id)

        if cid in self._connectors:
            conn = self._connectors[cid]
            if conn._connected:
                # If the connector has a pool attached to an old closed/different event loop, discard it
                pool = getattr(conn, "_pool", None)
                if pool is None or getattr(pool, "_loop", None) == asyncio.get_running_loop():
                    return conn
                self._connectors.pop(cid, None)

        async with self._lock:
            # Double check after acquiring lock
            if cid in self._connectors and self._connectors[cid]._connected:
                conn = self._connectors[cid]
                pool = getattr(conn, "_pool", None)
                if pool is None or getattr(pool, "_loop", None) == asyncio.get_running_loop():
                    return conn
                self._connectors.pop(cid, None)

            db_type = (credential_row.db_type or "").lower()
            connector_cls = DRIVER_MAP.get(db_type)
            if not connector_cls:
                raise ValueError(
                    f"Unsupported db_type '{credential_row.db_type}'. "
                    f"Supported types: {list(DRIVER_MAP.keys())}"
                )

            # Decrypt secret payload if present
            payload: Dict[str, Any] = {}
            if credential_row.encrypted_secret_payload:
                try:
                    payload = decrypt_credential_payload(credential_row.encrypted_secret_payload)
                except SecretDecryptionError:
                    logger.warning("Failed to decrypt credentials for credential_id %s", cid)

            config = {
                "host": credential_row.host,
                "port": credential_row.port,
                "database_name": credential_row.database_name,
                "username": credential_row.username,
                "is_read_only": credential_row.is_read_only,
                "max_connections": credential_row.max_connections,
                **payload,
            }

            connector = connector_cls(cid, config)
            await connector.connect()
            self._connectors[cid] = connector
            return connector

    async def remove_connector(self, credential_id: str) -> None:
        """Close and remove a cached connector."""
        async with self._lock:
            if credential_id in self._connectors:
                conn = self._connectors.pop(credential_id)
                try:
                    await conn.close()
                except Exception as exc:
                    logger.warning("Error closing connector %s: %s", credential_id, exc)

    async def close_all(self) -> None:
        """Close all managed connection pools."""
        async with self._lock:
            for cid, conn in list(self._connectors.items()):
                try:
                    await conn.close()
                except Exception as exc:
                    logger.warning("Error closing connector %s during shutdown: %s", cid, exc)
            self._connectors.clear()


async def get_connector(credential_row: Any) -> BaseDatabaseConnector:
    """Convenience helper to retrieve a cached connector from a database row."""
    manager = ConnectorPoolManager.get_instance()
    return await manager.get_connector(credential_row)
