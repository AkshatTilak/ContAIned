"""Real integration tests for Agent Invocation SSE streaming."""

from unittest.mock import MagicMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.utils import create_access_token
from tests.streaming.conftest import collect_all_events

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


async def _mock_async_stream_chunks(tokens: list[str]):
    """Helper to mock async litellm streaming generator response."""
    for tok in tokens:
        choice = MagicMock()
        choice.delta.content = tok
        chunk = MagicMock()
        chunk.choices = [choice]
        yield chunk


@pytest.mark.asyncio
async def test_agent_invoke_sse_stream_success(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Invoke agent with stream: true and verify chunk accumulation and [DONE] sentinel."""
    owner = await seed_user(email="stream_invoker@contained.ai", role="member")
    headers = await _auth_headers(owner)

    hub = await seed_hub(owner=owner, name="Agent Stream Hub", slug="agent-stream-hub", hub_type="agent")

    # Create agent
    agent_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/agents",
        json={
            "name": "Streaming Assistant",
            "role": "assistant",
            "system_prompt": "You are a helpful streaming assistant.",
            "model_id": "gemini/gemma-4-31b-it",
            "temperature": 0.3,
        },
        headers=headers,
    )
    assert agent_resp.status_code == 201
    agent_id = agent_resp.json()["id"]

    simulated_tokens = ["ContAIned ", "AI ", "Platform ", "is ", "supercharged."]
    with patch("gateway.api.agent_invoke.completion_with_fallback") as mock_litellm:
        mock_litellm.return_value = _mock_async_stream_chunks(simulated_tokens)

        events = await collect_all_events(
            gateway_client,
            f"/api/hubs/{hub.id}/agents/{agent_id}/invoke",
            method="POST",
            headers=headers,
            json_body={"prompt": "Explain ContAIned", "stream": True},
            timeout_s=5.0,
        )

    assert len(events) >= len(simulated_tokens) + 1  # tokens + completed + [DONE]

    deltas = [e["data"]["delta"] for e in events if isinstance(e.get("data"), dict) and "delta" in e["data"]]
    accumulated_text = "".join(deltas)
    assert accumulated_text == "ContAIned AI Platform is supercharged."

    # Verify final completed event
    completed_event = next(
        e for e in events if isinstance(e.get("data"), dict) and e["data"].get("status") == "completed"
    )
    assert completed_event["data"]["agent_id"] == agent_id
    assert "latency_ms" in completed_event["data"]

    # Verify [DONE] sentinel
    assert any(e.get("data") == "[DONE]" for e in events)


@pytest.mark.asyncio
async def test_agent_invoke_sse_inactive_error(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Invoke inactive agent with stream: true and verify 403 Forbidden."""
    owner = await seed_user(email="inactive_stream_user@contained.ai", role="member")
    headers = await _auth_headers(owner)

    hub = await seed_hub(owner=owner, name="Inactive Hub", slug="inactive-hub", hub_type="agent")

    agent_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/agents",
        json={
            "name": "Sleeping Agent",
            "role": "bot",
            "system_prompt": "Quiet",
            "model_id": "gemini/gemma-4-26b-a4b-it",
            "is_active": False,
        },
        headers=headers,
    )
    agent_id = agent_resp.json()["id"]

    resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/agents/{agent_id}/invoke",
        json={"prompt": "Wake up", "stream": True},
        headers=headers,
    )
    assert resp.status_code == 403
