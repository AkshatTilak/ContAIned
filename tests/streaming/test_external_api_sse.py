"""Real integration tests for OpenAI-compatible External API (/v1/chat/completions) SSE streaming."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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
async def test_external_chat_completions_sse_stream(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Call /v1/chat/completions with API key and stream: true, verifying OpenAI-compliant chunk structure."""
    admin = await seed_user(email="api_admin@contained.ai", role="admin")
    admin_headers = await _auth_headers(admin)

    # Create real API Key via endpoint
    key_resp = await gateway_client.post(
        "/api/settings/api-keys",
        json={"name": "Streaming Integration Key"},
        headers=admin_headers,
    )
    assert key_resp.status_code == 201, f"Failed to create API key: {key_resp.text}"
    raw_key = key_resp.json().get("raw_key") or key_resp.json().get("key")

    headers = {"Authorization": f"Bearer {raw_key}"}
    simulated_tokens = ["Hello ", "OpenAI ", "compatible ", "streaming ", "world!"]

    @asynccontextmanager
    async def _mock_db_factory():
        yield real_db_session

    with patch("gateway.auth.api_key_middleware.get_sessionmaker", return_value=_mock_db_factory):
        with patch("gateway.api.external.completion_with_fallback", new_callable=AsyncMock) as mock_litellm:
            mock_litellm.return_value = _mock_chunk_list(simulated_tokens)

            payload = {
                "model": "gemini/gemma-4-31b-it",
                "messages": [{"role": "user", "content": "Say hello"}],
                "stream": True,
                "temperature": 0.7,
            }

            events = await collect_all_events(
                gateway_client,
                "/v1/chat/completions",
                method="POST",
                headers=headers,
                json_body=payload,
                timeout_s=5.0,
            )

    assert len(events) >= len(simulated_tokens)

    # Validate first role header chunk
    first_chunk = next(e for e in events if isinstance(e.get("data"), dict) and "choices" in e["data"])
    assert first_chunk["data"]["object"] == "chat.completion.chunk"
    assert first_chunk["data"]["model"] == "gemini/gemma-4-31b-it"

    # Validate content accumulation
    content_pieces = []
    for e in events:
        data = e.get("data")
        if isinstance(data, dict) and "choices" in data:
            delta = data["choices"][0].get("delta", {})
            if "content" in delta and delta["content"]:
                content_pieces.append(delta["content"])

    assert "".join(content_pieces) == "Hello OpenAI compatible streaming world!"

    # Validate stop chunk
    stop_chunk = next(
        e
        for e in events
        if isinstance(e.get("data"), dict)
        and "choices" in e["data"]
        and e["data"]["choices"][0].get("finish_reason") == "stop"
    )
    assert stop_chunk is not None

    # Validate [DONE]
    assert any(e.get("data") == "[DONE]" for e in events)


@pytest.mark.asyncio
async def test_external_chat_completions_sse_missing_key(gateway_client: AsyncClient):
    """Calling /v1/chat/completions without API key returns 401 Unauthorized."""
    resp = await gateway_client.post(
        "/v1/chat/completions",
        json={"model": "gemini/gemma-4-26b-a4b-it", "messages": [{"role": "user", "content": "Hi"}], "stream": True},
    )
    assert resp.status_code == 401
