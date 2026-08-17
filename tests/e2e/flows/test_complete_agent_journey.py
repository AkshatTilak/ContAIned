"""End-to-End Test: Complete Agent Journey from registration to playground and evaluation."""

import uuid
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_complete_agent_journey(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Full lifecycle: signup -> agent hub -> agent creation -> link ingestion -> invoke -> eval."""
    uid = uuid.uuid4().hex[:8]
    owner = await seed_user(email=f"agent_journey_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(owner)

    # 1. Create Agent Hub
    hub_resp = await gateway_client.post(
        "/api/hubs",
        json={
            "name": f"Agent Hub {uid}",
            "slug": f"agent-hub-{uid}",
            "description": "E2E Agent Journey Hub",
            "hub_type": "agent",
        },
        headers=headers,
    )
    assert hub_resp.status_code == 201
    agent_hub = hub_resp.json()
    agent_hub_id = agent_hub["id"]

    # 2. Create Ingestion Hub & Collection
    ingest_hub_resp = await gateway_client.post(
        "/api/hubs",
        json={
            "name": f"Knowledge Hub {uid}",
            "slug": f"knowledge-hub-{uid}",
            "description": "E2E Knowledge Base",
            "hub_type": "ingestion",
        },
        headers=headers,
    )
    assert ingest_hub_resp.status_code == 201
    ingest_hub_id = ingest_hub_resp.json()["id"]

    # Create collection under /api/hubs/{ingest_hub_id}/ingestion/collections
    col_resp = await gateway_client.post(
        f"/api/hubs/{ingest_hub_id}/ingestion/collections",
        json={
            "name": f"E2E Collection {uid}",
            "description": "Agent knowledge collection",
            "embedder": "gemini/gemini-embedding-2",
        },
        headers=headers,
    )
    assert col_resp.status_code == 201
    collection_id = col_resp.json()["id"]

    # 3. Link Ingestion Hub to Agent Hub
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

    # 4. Create Agent with Collection Binding & Distributed Model (gemma-4-31b-it)
    agent_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub_id}/agents",
        json={
            "name": f"Analyst Assistant {uid}",
            "slug": f"analyst-assistant-{uid}",
            "role": "analyst",
            "system_prompt": "You are a senior analyst providing precise responses.",
            "model_id": "gemini/gemma-4-31b-it",
            "temperature": 0.3,
            "max_tokens": 1024,
            "collection_bindings": [
                {
                    "hub_id": ingest_hub_id,
                    "collection_id": collection_id,
                    "top_k": 3,
                    "score_threshold": 0.5,
                }
            ],
        },
        headers=headers,
    )
    assert agent_resp.status_code == 201
    agent = agent_resp.json()
    agent_id = agent["id"]

    # 5. Invoke Agent via Non-Streaming Call
    with patch("gateway.api.agent_invoke.completion_with_fallback", new_callable=AsyncMock) as mock_complete:
        mock_choice = AsyncMock()
        mock_choice.message.content = "E2E agent execution successful with analysis."
        mock_resp = AsyncMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage = AsyncMock(prompt_tokens=25, completion_tokens=15, total_tokens=40)
        mock_complete.return_value = mock_resp

        invoke_resp = await gateway_client.post(
            f"/api/hubs/{agent_hub_id}/agents/{agent_id}/invoke",
            json={"prompt": "Analyze system telemetry data."},
            headers=headers,
        )
        assert invoke_resp.status_code == 200
        invoke_data = invoke_resp.json()
        assert invoke_data["agent_id"] == agent_id
        assert "E2E agent execution" in invoke_data["response"]

    # 6. Create Eval Hub & Link to Agent Hub
    eval_hub_resp = await gateway_client.post(
        "/api/hubs",
        json={
            "name": f"Eval Hub {uid}",
            "slug": f"eval-hub-{uid}",
            "description": "Evaluation pipelines",
            "hub_type": "eval",
        },
        headers=headers,
    )
    assert eval_hub_resp.status_code == 201
    eval_hub_id = eval_hub_resp.json()["id"]

    # Link Eval Hub to Agent Hub
    eval_link_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub_id}/links",
        json={
            "target_hub_id": agent_hub_id,
            "permission": "read",
        },
        headers=headers,
    )
    assert eval_link_resp.status_code == 201

    # Create Suite in Eval Hub
    suite_resp = await gateway_client.post(
        f"/api/hubs/{eval_hub_id}/eval/suites",
        json={
            "name": f"Agent Benchmark Suite {uid}",
            "description": "Benchmark suite for analyst agent",
            "target": {
                "type": "agent",
                "target_hub_id": agent_hub_id,
                "target_id": agent_id,
            },
        },
        headers=headers,
    )
    assert suite_resp.status_code == 201

    # Verify everything linked and queryable
    agents_list_resp = await gateway_client.get(f"/api/hubs/{agent_hub_id}/agents", headers=headers)
    assert agents_list_resp.status_code == 200
    assert any(a["id"] == agent_id for a in agents_list_resp.json())
