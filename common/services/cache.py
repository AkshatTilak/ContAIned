"""Redis Caching Service Layer (B8-11 / sub_11_01).

Provides centralized async caching for Hub metadata, User sessions, Model registry, and Collection schemas.
"""

import json
import logging
from typing import Any, Optional

from common.clients.redis import get_redis_client

logger = logging.getLogger("common.services.cache")


# ---------------------------------------------------------------------------
# Core Cache Primitives
# ---------------------------------------------------------------------------

async def cache_get_json(key: str) -> Optional[Any]:
    """Retrieve JSON-deserialized object from Redis."""
    try:
        redis = get_redis_client()
        raw = await redis.get(key)
        if raw is not None:
            logger.debug("Cache HIT for key: %s", key)
            return json.loads(raw)
        logger.debug("Cache MISS for key: %s", key)
        return None
    except Exception as e:
        logger.warning("Cache GET failed for key %s: %s", key, e)
        return None


async def cache_set_json(key: str, data: Any, ttl_seconds: int = 300) -> bool:
    """Serialize and store object in Redis with TTL."""
    try:
        redis = get_redis_client()
        serialized = json.dumps(data)
        await redis.set(key, serialized, ex=ttl_seconds)
        logger.debug("Cache SET for key: %s (TTL: %ds)", key, ttl_seconds)
        return True
    except Exception as e:
        logger.warning("Cache SET failed for key %s: %s", key, e)
        return False


async def cache_delete(key: str) -> bool:
    """Delete a single key from Redis."""
    try:
        redis = get_redis_client()
        await redis.delete(key)
        logger.debug("Cache INVALIDATED for key: %s", key)
        return True
    except Exception as e:
        logger.warning("Cache DELETE failed for key %s: %s", key, e)
        return False


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching glob pattern."""
    try:
        redis = get_redis_client()
        keys = await redis.keys(pattern)
        if keys:
            deleted = await redis.delete(*keys)
            logger.debug("Cache INVALIDATED %d key(s) matching %s", deleted, pattern)
            return deleted
        return 0
    except Exception as e:
        logger.warning("Cache DELETE PATTERN failed for %s: %s", pattern, e)
        return 0


# ---------------------------------------------------------------------------
# Domain Cache Helpers
# ---------------------------------------------------------------------------

# 1. Hub Metadata Cache
def _hub_id_key(hub_id: str) -> str:
    return f"cache:hub:id:{hub_id}"


def _hub_slug_key(slug: str) -> str:
    return f"cache:hub:slug:{slug}"


async def get_cached_hub_by_id(hub_id: str) -> Optional[dict]:
    return await cache_get_json(_hub_id_key(hub_id))


async def get_cached_hub_by_slug(slug: str) -> Optional[dict]:
    return await cache_get_json(_hub_slug_key(slug))


async def cache_hub_metadata(hub_id: str, slug: str, hub_dict: dict, ttl: int = 300) -> None:
    await cache_set_json(_hub_id_key(hub_id), hub_dict, ttl_seconds=ttl)
    await cache_set_json(_hub_slug_key(slug), hub_dict, ttl_seconds=ttl)


async def invalidate_hub_cache(hub_id: str, slug: Optional[str] = None) -> None:
    await cache_delete(_hub_id_key(hub_id))
    if slug:
        await cache_delete(_hub_slug_key(slug))


# 2. User Session Cache
def _user_session_key(user_id: str) -> str:
    return f"cache:user:{user_id}"


async def get_cached_user(user_id: str) -> Optional[dict]:
    return await cache_get_json(_user_session_key(user_id))


async def cache_user(user_id: str, user_dict: dict, ttl: int = 600) -> None:
    await cache_set_json(_user_session_key(user_id), user_dict, ttl_seconds=ttl)


async def invalidate_user_cache(user_id: str) -> None:
    await cache_delete(_user_session_key(user_id))


# 3. Model Registry Cache
MODEL_REGISTRY_KEY = "cache:models:registry"


async def get_cached_model_registry() -> Optional[dict]:
    return await cache_get_json(MODEL_REGISTRY_KEY)


async def cache_model_registry(registry_dict: dict, ttl: int = 300) -> None:
    await cache_set_json(MODEL_REGISTRY_KEY, registry_dict, ttl_seconds=ttl)


async def invalidate_model_registry_cache() -> None:
    await cache_delete(MODEL_REGISTRY_KEY)


# 4. Qdrant Collection Schema Cache
def _collection_schema_key(collection_name: str) -> str:
    return f"cache:collection:schema:{collection_name}"


async def get_cached_collection_schema(collection_name: str) -> Optional[dict]:
    return await cache_get_json(_collection_schema_key(collection_name))


async def cache_collection_schema(collection_name: str, schema_dict: dict, ttl: int = 300) -> None:
    await cache_set_json(_collection_schema_key(collection_name), schema_dict, ttl_seconds=ttl)


async def invalidate_collection_schema_cache(collection_name: str) -> None:
    await cache_delete(_collection_schema_key(collection_name))
