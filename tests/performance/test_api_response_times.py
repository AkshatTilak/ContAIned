"""API Response Time Benchmark Tests (B8-13 / sub_13_01).

Benchmarks response latencies for health, hub listing, and agent/workflow creation.
"""

import time
import uuid
import pytest
from httpx import AsyncClient

from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.performance


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_health_endpoint_response_time(gateway_client: AsyncClient):
    """Verify health endpoint responds within fast benchmark window (< 2000ms in live integration)."""
    start = time.perf_counter()
    resp = await gateway_client.get("/health")
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert resp.status_code in (200, 503)
    assert elapsed_ms < 2000.0, f"Health endpoint took {elapsed_ms:.2f}ms"


@pytest.mark.asyncio
async def test_hub_list_response_time(gateway_client: AsyncClient, seed_user):
    """Verify hub list endpoint responds quickly."""
    uid = uuid.uuid4().hex[:8]
    user = await seed_user(email=f"bench_user_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(user)

    # Warmup / seed one hub
    await gateway_client.post(
        "/api/hubs",
        json={"name": f"Bench Hub {uid}", "slug": f"bench-hub-{uid}", "hub_type": "agent"},
        headers=headers,
    )

    start = time.perf_counter()
    resp = await gateway_client.get("/api/hubs", headers=headers)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert resp.status_code == 200
    assert elapsed_ms < 1500.0, f"Hub list endpoint took {elapsed_ms:.2f}ms"


@pytest.mark.asyncio
async def test_agent_crud_response_time(gateway_client: AsyncClient, seed_user):
    """Verify agent creation responds quickly with distributed model configuration."""
    uid = uuid.uuid4().hex[:8]
    user = await seed_user(email=f"bench_agent_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(user)

    hub_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": f"Agent Bench Hub {uid}", "slug": f"agent-bench-{uid}", "hub_type": "agent"},
        headers=headers,
    )
    hub_id = hub_resp.json()["id"]

    start = time.perf_counter()
    resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/agents",
        json={
            "name": f"Fast Bench Agent {uid}",
            "role": "worker",
            "model_id": "gemini/gemma-4-31b-it",
            "system_prompt": "You are a performance testing agent.",
        },
        headers=headers,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert resp.status_code == 201
    assert elapsed_ms < 2000.0, f"Agent creation took {elapsed_ms:.2f}ms"
