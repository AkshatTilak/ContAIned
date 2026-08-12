"""Async database connector pool package for Task 12 external database integrations.

Exports:
    BaseDatabaseConnector — abstract base class.
    PostgresConnector     — asyncpg/SQLAlchemy async driver.
    MySQLConnector        — aiomysql driver.
    MongoConnector        — motor driver.
    RedisConnector        — redis-py async driver.
    ConnectorPoolManager  — singleton that caches connectors per credential_id.
    get_connector         — convenience factory from ExternalCredential row.
"""

from common.clients.db_connectors.base import BaseDatabaseConnector
from common.clients.db_connectors.postgres import PostgresConnector
from common.clients.db_connectors.mysql import MySQLConnector
from common.clients.db_connectors.mongo import MongoConnector
from common.clients.db_connectors.redis import RedisConnector
from common.clients.db_connectors.pool_manager import ConnectorPoolManager, get_connector

__all__ = [
    "BaseDatabaseConnector",
    "PostgresConnector",
    "MySQLConnector",
    "MongoConnector",
    "RedisConnector",
    "ConnectorPoolManager",
    "get_connector",
]
