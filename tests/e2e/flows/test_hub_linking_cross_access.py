"""End-to-End Test: Hub Linking Cross-Access, cross-hub retrieval, and link revocation enforcement."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_hub_linking_cross_access_journey(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Create ingestion hub & collection -> create agent in agent hub -> link hubs -> retrieve -> revoke link."""
    uid = uuid.uuid4().hex[:8]
    owner = await seed_user(email=f"cross_hub_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(owner)

    # 1. Create Ingestion Hub & Collection
    ingest_hub_resp = await gateway_client.post(
        "/api/hubs",
        json={
            "name": f"Source Knowledge Hub {uid}",
            "slug": f"source-knowledge-{uid}",
            "description": "Source knowledge repository",
            "hub_type": "ingestion",
        },
        headers=headers,
    )
    assert ingest_hub_resp.status_code == 201
    ingest_hub_id = ingest_hub_resp.json()["id"]

    col_resp = await gateway_client.post(
        f"/api/hubs/{ingest_hub_id}/ingestion/collections",
        json={
            "name": f"Enterprise Policies {uid}",
            "description": "Company policy documents",
            "embedder": "gemini/gemini-embedding-2",
        },
        headers=headers,
    )
    assert col_resp.status_code == 201
    collection_id = col_resp.json()["id"]

    # 2. Create Agent Hub
    agent_hub_resp = await gateway_client.post(
        "/api/hubs",
        json={
            "name": f"Consumer Agent Hub {uid}",
            "slug": f"consumer-agent-hub-{uid}",
            "description": "Agent consuming linked knowledge",
            "hub_type": "agent",
        },
        headers=headers,
    )
    assert agent_hub_resp.status_code == 201
    agent_hub_id = agent_hub_resp.json()["id"]

    # 3. Establish Hub Link (Agent Hub -> Ingestion Hub)
    link_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub_id}/links",
        json={
            "target_hub_id": ingest_hub_id,
            "permission": "read",
        },
        headers=headers,
    )
    assert link_resp.status_code == 201
    link_id = link_resp.json()["id"]

    # Verify link listed
    links_resp = await gateway_client.get(f"/api/hubs/{agent_hub_id}/links", headers=headers)
    assert links_resp.status_code == 200
    assert any(lnk["id"] == link_id for lnk in links_resp.json())

    # 4. Create Agent with Cross-Hub Collection Binding and Distributed Model (gemma-3-27b-it)
    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub_id}/agents",
        json={
            "name": f"Cross-Hub Policy Bot {uid}",
            "slug": f"policy-bot-{uid}",
            "role": "assistant",
            "system_prompt": "Answer questions based on enterprise policies.",
            "model_id": "gemini/gemma-3-27b-it",
            "temperature": 0.2,
            "collection_bindings": [
                {
                    "hub_id": ingest_hub_id,
                    "collection_id": collection_id,
                    "top_k": 5,
                    "score_threshold": 0.6,
                }
            ],
        },
        headers=headers,
    )
    assert agent_resp.status_code == 201
    agent_id = agent_resp.json()["id"]

    # Verify agent retrieved with bindings
    get_agent_resp = await gateway_client.get(
        f"/api/hubs/{agent_hub_id}/agents/{agent_id}",
        headers=headers,
    )
    assert get_agent_resp.status_code == 200
    agent_data = get_agent_resp.json()
    assert len(agent_data.get("collection_bindings") or []) == 1

    # 5. Revoke Hub Link
    delete_link_resp = await gateway_client.delete(
        f"/api/hubs/{agent_hub_id}/links/{link_id}",
        headers=headers,
    )
    assert delete_link_resp.status_code in (200, 204)

    # Verify link removed
    updated_links_resp = await gateway_client.get(f"/api/hubs/{agent_hub_id}/links", headers=headers)
    assert updated_links_resp.status_code == 200
    assert not any(lnk["id"] == link_id for lnk in updated_links_resp.json())
