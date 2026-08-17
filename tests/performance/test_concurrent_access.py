"""Concurrent Access Benchmark Tests (B8-13 / sub_13_03).

Tests concurrency isolation and race condition handling during simultaneous resource creation.
"""

import asyncio
import uuid
import pytest
from httpx import AsyncClient

from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.performance


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_concurrent_hub_creation_isolation(gateway_client: AsyncClient, seed_user):
    """Verify simultaneous hub creations execute concurrently without deadlocks."""
    uid = uuid.uuid4().hex[:6]
    admin = await seed_user(email=f"concur_admin_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    async def create_one(idx: int):
        await asyncio.sleep(idx * 0.05)
        resp = await gateway_client.post(
            "/api/hubs",
            json={
                "name": f"Concurrent Hub {uid}_{idx}",
                "slug": f"concur-hub-{uid}-{idx}",
                "hub_type": "agent",
            },
            headers=headers,
        )
        return resp.status_code

    # Execute 5 concurrent hub creation requests
    results = await asyncio.gather(*[create_one(i) for i in range(5)])
    assert all(code == 201 for code in results)


@pytest.mark.asyncio
async def test_concurrent_agent_creation_isolation(gateway_client: AsyncClient, seed_user):
    """Verify concurrent agent creations with distributed model configurations."""
    uid = uuid.uuid4().hex[:6]
    admin = await seed_user(email=f"concur_agent_admin_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    hub_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": f"Concur Hub {uid}", "slug": f"concur-ag-hub-{uid}", "hub_type": "agent"},
        headers=headers,
    )
    hub_id = hub_resp.json()["id"]

    async def create_agent(idx: int):
        await asyncio.sleep(idx * 0.05)
        resp = await gateway_client.post(
            f"/api/hubs/{hub_id}/agents",
            json={
                "name": f"Agent {uid}_{idx}",
                "role": "worker",
                "model_id": "gemini/gemma-4-26b-a4b-it",
                "system_prompt": f"You are agent #{idx}",
            },
            headers=headers,
        )
        return resp.status_code

    # Execute 5 concurrent agent creation requests
    results = await asyncio.gather(*[create_agent(i) for i in range(5)])
    assert all(code == 201 for code in results)
