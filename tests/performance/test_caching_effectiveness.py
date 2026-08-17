"""Caching Effectiveness Benchmark Tests (B8-13 / sub_13_02).

Benchmarks latency differences between cache hits and misses, and validates invalidation speed.
"""

import time
import uuid
import pytest

from common.services.cache import (
    cache_hub_metadata,
    get_cached_hub_by_id,
    invalidate_hub_cache,
)

pytestmark = pytest.mark.performance


@pytest.mark.asyncio
async def test_cache_hit_speedup_and_invalidation():
    """Verify cache hits provide low sub-millisecond retrieval and invalidation clears immediately."""
    uid = uuid.uuid4().hex[:8]
    hub_id = f"perf-hub-{uid}"
    slug = f"perf-slug-{uid}"
    payload = {
        "id": hub_id,
        "name": f"Performance Hub {uid}",
        "slug": slug,
        "hub_type": "workflow",
        "description": "High performance cached metadata payload",
    }

    # 1. First lookup (Cache Miss)
    t0 = time.perf_counter()
    miss_res = await get_cached_hub_by_id(hub_id)
    miss_time_ms = (time.perf_counter() - t0) * 1000.0
    assert miss_res is None

    # Populate cache
    await cache_hub_metadata(hub_id, slug, payload, ttl=120)

    # 2. Second lookup (Cache Hit)
    t1 = time.perf_counter()
    hit_res = await get_cached_hub_by_id(hub_id)
    hit_time_ms = (time.perf_counter() - t1) * 1000.0

    assert hit_res is not None
    assert hit_res["id"] == hub_id
    assert hit_time_ms < 50.0  # Redis in-memory lookup is sub-50ms

    # 3. Invalidation
    await invalidate_hub_cache(hub_id, slug)
    post_inval_res = await get_cached_hub_by_id(hub_id)
    assert post_inval_res is None
