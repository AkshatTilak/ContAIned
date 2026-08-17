"""Real integration tests for Playground Chat SSE streaming."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient

from gateway.auth.utils import create_access_token
from tests.streaming.conftest import collect_all_events

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


def _mock_chunk_list(tokens: list[str]):
    """Helper to return a list of mock chunk objects."""
    chunks = []
    for tok in tokens:
        choice = MagicMock()
        choice.delta.content = tok
        chunk = MagicMock()
        chunk.choices = [choice]
        chunks.append(chunk)
    return chunks


@pytest.mark.asyncio
async def test_playground_chat_sse_streaming(gateway_client: AsyncClient, seed_user):
    """Verify streaming playground chat returns delta chunks and finishes with [DONE]."""
    user = await seed_user(email="playground_streamer@contained.ai", role="member")
    headers = await _auth_headers(user)
    simulated_tokens = ["ContAIned ", "Playground ", "SSE ", "works ", "seamlessly."]

    with patch("gateway.api.playground.completion_with_fallback", new_callable=AsyncMock) as mock_litellm:
        mock_litellm.return_value = _mock_chunk_list(simulated_tokens)

        payload = {
            "model_id": "gemini/gemma-4-31b-it",
            "messages": [{"role": "user", "content": "Tell me about Playground"}],
            "stream": True,
            "temperature": 0.5,
            "max_tokens": 512,
        }

        events = await collect_all_events(
            gateway_client,
            "/api/playground/chat",
            method="POST",
            headers=headers,
            json_body=payload,
            timeout_s=5.0,
        )

    assert len(events) >= len(simulated_tokens)

    # Accumulate chunks
    deltas = [
        e["data"]["content"]
        for e in events
        if isinstance(e.get("data"), dict) and "content" in e["data"]
    ]
    assert "".join(deltas) == "ContAIned Playground SSE works seamlessly."

    # Verify [DONE] sentinel
    assert any(e.get("data") == "[DONE]" for e in events)


@pytest.mark.asyncio
async def test_playground_chat_sse_with_custom_system_prompt(gateway_client: AsyncClient, seed_user):
    """Verify system prompt is prepended and tokens are streamed."""
    user = await seed_user(email="playground_prompt@contained.ai", role="member")
    headers = await _auth_headers(user)
    tokens = ["Hello ", "from ", "specialized ", "persona."]
    with patch("gateway.api.playground.completion_with_fallback", new_callable=AsyncMock) as mock_litellm:
        mock_litellm.return_value = _mock_chunk_list(tokens)

        payload = {
            "model_id": "gemini/gemma-4-26b-a4b-it",
            "system_prompt": "You are a specialized legal assistant.",
            "messages": [{"role": "user", "content": "Draft intro"}],
            "stream": True,
        }

        events = await collect_all_events(
            gateway_client,
            "/api/playground/chat",
            method="POST",
            headers=headers,
            json_body=payload,
            timeout_s=5.0,
        )

    deltas = [e["data"]["content"] for e in events if isinstance(e.get("data"), dict) and "content" in e["data"]]
    assert "".join(deltas) == "Hello from specialized persona."
    assert any(e.get("data") == "[DONE]" for e in events)


@pytest.mark.asyncio
async def test_playground_chat_sse_error_handling(gateway_client: AsyncClient, seed_user):
    """Verify streaming error produces error JSON in stream."""
    user = await seed_user(email="playground_err@contained.ai", role="member")
    headers = await _auth_headers(user)
    with patch("gateway.api.playground.completion_with_fallback", side_effect=RuntimeError("Provider offline")):
        payload = {
            "model_id": "gemini/gemma-3-27b-it",
            "messages": [{"role": "user", "content": "Crash test"}],
            "stream": True,
        }

        events = await collect_all_events(
            gateway_client,
            "/api/playground/chat",
            method="POST",
            headers=headers,
            json_body=payload,
            timeout_s=5.0,
        )

    assert len(events) >= 1
    err_event = next(e for e in events if isinstance(e.get("data"), dict) and "error" in e["data"])
    assert "Provider offline" in err_event["data"]["error"]
