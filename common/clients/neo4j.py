"""Neo4j graph database client wrapper.

Provides connection pooling, read-only session enforcement,
and parameterized queries for namespaced submodules.
"""

import asyncio
import logging
import re
from typing import Any, AsyncGenerator, Optional
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from common.config.settings import settings

logger = logging.getLogger("common.neo4j")

_driver: Optional[AsyncDriver] = None


def get_neo4j_driver() -> AsyncDriver:
    """Get or initialize the global Neo4j asynchronous driver."""
    global _driver
    if _driver is None:
        try:
            _driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URL,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                keep_alive=True,
            )
            logger.info("Neo4j async driver initialized.")
        except Exception as e:
            logger.error("Failed to initialize Neo4j driver: %s", e)
            raise RuntimeError("Neo4j driver initialization failed") from e
    return _driver


async def close_neo4j() -> None:
    """Close the global Neo4j driver."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
        logger.info("Neo4j async driver closed.")


def enforce_read_only_query(query: str) -> None:
    """Block Cypher queries containing write commands.

    Raises:
        ValueError: If a write command is detected.
    """
    # Check for Cypher write operations: CREATE, MERGE, DELETE, SET, REMOVE, DROP
    forbidden = r"\b(CREATE|MERGE|DELETE|SET|REMOVE|DROP)\b"
    if re.search(forbidden, query, re.IGNORECASE):
        logger.error("Forbidden write statement detected in read-only Cypher query: %s", query)
        raise ValueError("Write statements are not allowed in read-only Cypher queries.")


async def execute_read_query(query: str, parameters: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Execute a parameterized Cypher read query and return the results as a list of dicts.

    Ensures read-only query protections.
    """
    enforce_read_only_query(query)
    driver = get_neo4j_driver()
    parameters = parameters or {}
    
    async with driver.session() as session:
        result = await session.run(query, parameters)
        records = await result.data()
        return records


async def get_neo4j_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency generator yielding an active Neo4j session.

    Session lifecycle is cleanly managed.
    """
    driver = get_neo4j_driver()
    async with driver.session() as session:
        yield session


async def verify_neo4j_connection(max_retries: int = 5, backoff_factor: float = 2.0) -> None:
    """Verify Neo4j connection with exponential backoff on startup."""
    driver = get_neo4j_driver()
    retries = 0
    delay = 1.0
    while retries < max_retries:
        try:
            await driver.verify_connectivity()
            logger.info("Neo4j connection verified successfully.")
            return
        except Exception as e:
            retries += 1
            if retries >= max_retries:
                logger.error("Failed to connect to Neo4j after %d attempts: %s", max_retries, e)
                raise ConnectionError("Neo4j is unreachable") from e
            logger.warning(
                "Neo4j connection attempt %d failed. Retrying in %.2f seconds... Error: %s",
                retries, delay, e
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor
