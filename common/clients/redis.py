"""Redis database client wrapper.

Provides async Redis access for caching, rate limiting, and session storage.
Shared across all projects and backends.
"""

import asyncio
import logging
from typing import Optional
import redis.asyncio as aioredis

from common.config.settings import settings

logger = logging.getLogger("common.redis")

_redis_client: Optional[aioredis.Redis] = None


def get_redis_client() -> aioredis.Redis:
    """Get or initialize the global Redis client."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                encoding="utf-8"
            )
            logger.info("Redis async client initialized.")
        except Exception as e:
            logger.error("Failed to initialize Redis client: %s", e)
            raise RuntimeError("Redis initialization failed") from e
    return _redis_client


async def close_redis() -> None:
    """Close the global Redis client connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis async client connection closed.")


async def verify_redis_connection(max_retries: int = 5, backoff_factor: float = 2.0) -> None:
    """Verify Redis connection with exponential backoff on startup."""
    client = get_redis_client()
    retries = 0
    delay = 1.0
    while retries < max_retries:
        try:
            await client.ping()
            logger.info("Redis connection verified successfully.")
            return
        except Exception as e:
            retries += 1
            if retries >= max_retries:
                logger.error("Failed to connect to Redis after %d attempts: %s", max_retries, e)
                raise ConnectionError("Redis is unreachable") from e
            logger.warning(
                "Redis connection attempt %d failed. Retrying in %.2f seconds... Error: %s",
                retries, delay, e
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor
