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


import json
from typing import Callable, Any


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


async def publish_event(channel: str, message: dict[str, Any]) -> int:
    """Publish a JSON payload to a Redis Pub/Sub channel."""
    try:
        client = get_redis_client()
        payload = json.dumps(message)
        recipients = await client.publish(channel, payload)
        logger.info("Published Redis event to channel '%s' (%d subscriber(s) received)", channel, recipients)
        return recipients
    except Exception as e:
        logger.warning("Failed to publish Redis event to channel '%s': %s", channel, e)
        return 0


async def subscribe_channel(channel: str, callback: Callable[[dict[str, Any]], Any]) -> None:
    """Subscribe to a Redis channel and invoke callback on incoming messages."""
    try:
        client = get_redis_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)
        logger.info("Subscribed to Redis channel '%s'", channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as cb_err:
                    logger.error("Callback failed for Redis channel '%s': %s", channel, cb_err)
    except asyncio.CancelledError:
        logger.info("Redis subscription to channel '%s' cancelled.", channel)
    except Exception as e:
        logger.error("Redis pubsub listener for channel '%s' encountered error: %s", channel, e)

