"""Real-world Redis Caching Layer Integration Tests (B8-11 / sub_11_01).

Tests Redis caching and invalidation for hubs, user sessions, model registry, and collection schemas.
"""

import uuid
import pytest

from common.services.cache import (
    cache_hub_metadata,
    get_cached_hub_by_id,
    get_cached_hub_by_slug,
    invalidate_hub_cache,
    cache_user,
    get_cached_user,
    invalidate_user_cache,
    cache_model_registry,
    get_cached_model_registry,
    invalidate_model_registry_cache,
    cache_collection_schema,
    get_cached_collection_schema,
    invalidate_collection_schema_cache,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_hub_metadata_caching_and_invalidation():
    """Verify hub caching by ID and slug, and cache invalidation."""
    uid = uuid.uuid4().hex[:8]
    hub_id = f"hub-{uid}"
    slug = f"analytics-hub-{uid}"
    hub_data = {"id": hub_id, "name": f"Analytics {uid}", "slug": slug, "hub_type": "agent"}

    # Set cache
    await cache_hub_metadata(hub_id, slug, hub_data, ttl=60)

    # Verify cache hits
    hit_by_id = await get_cached_hub_by_id(hub_id)
    assert hit_by_id is not None
    assert hit_by_id["name"] == hub_data["name"]

    hit_by_slug = await get_cached_hub_by_slug(slug)
    assert hit_by_slug is not None
    assert hit_by_slug["id"] == hub_id

    # Invalidate cache
    await invalidate_hub_cache(hub_id, slug)
    assert (await get_cached_hub_by_id(hub_id)) is None
    assert (await get_cached_hub_by_slug(slug)) is None


@pytest.mark.asyncio
async def test_user_session_caching():
    """Verify user session caching and invalidation."""
    uid = uuid.uuid4().hex[:8]
    user_id = f"user-{uid}"
    user_data = {"id": user_id, "email": f"cached_{uid}@contained.ai", "platform_role": "admin"}

    await cache_user(user_id, user_data, ttl=60)
    cached = await get_cached_user(user_id)
    assert cached is not None
    assert cached["email"] == user_data["email"]

    await invalidate_user_cache(user_id)
    assert (await get_cached_user(user_id)) is None


@pytest.mark.asyncio
async def test_model_registry_caching():
    """Verify model registry caching and invalidation."""
    registry_data = {
        "completion": {"active": {"model_id": "gemini/gemma-4-31b-it"}, "available": []},
        "embedding": {"active": {"model_id": "gemini/gemini-embedding-2"}, "available": []},
    }

    await cache_model_registry(registry_data, ttl=60)
    cached = await get_cached_model_registry()
    assert cached is not None
    assert "completion" in cached

    await invalidate_model_registry_cache()
    assert (await get_cached_model_registry()) is None


@pytest.mark.asyncio
async def test_collection_schema_caching():
    """Verify collection schema caching and invalidation."""
    col_name = f"col_docs_{uuid.uuid4().hex[:6]}"
    schema_data = {"vector_size": 768, "distance": "Cosine", "points_count": 42}

    await cache_collection_schema(col_name, schema_data, ttl=60)
    cached = await get_cached_collection_schema(col_name)
    assert cached is not None
    assert cached["vector_size"] == 768

    await invalidate_collection_schema_cache(col_name)
    assert (await get_cached_collection_schema(col_name)) is None
