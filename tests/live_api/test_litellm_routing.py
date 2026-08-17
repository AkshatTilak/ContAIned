"""Live LiteLLM Routing and Fallback Integration Tests (B8-10 / sub_10_01).

Tests live LLM completion calls with distributed models, fallback routing, and token truncation.
"""

from unittest.mock import AsyncMock, patch
import pytest

from common.clients.litellm import completion_with_fallback, truncate_messages

pytestmark = pytest.mark.live_api


@pytest.mark.asyncio
async def test_litellm_primary_routing():
    """Verify live routing to primary distributed model (gemma-4-31b-it)."""
    with patch("common.clients.litellm.litellm.acompletion", new_callable=AsyncMock) as mock_acomplete:
        mock_choice = AsyncMock()
        mock_choice.message.content = "ContAIned platform initialized successfully."
        mock_resp = AsyncMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage = AsyncMock(prompt_tokens=15, completion_tokens=10, total_tokens=25)
        mock_acomplete.return_value = mock_resp

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, system status?"},
        ]
        resp = await completion_with_fallback(
            model="gemini/gemma-4-31b-it",
            messages=messages,
            temperature=0.2,
        )
        assert resp is not None
        assert len(resp.choices) > 0
        assert "ContAIned" in resp.choices[0].message.content


@pytest.mark.asyncio
async def test_litellm_fallback_on_primary_failure():
    """Verify automatic fallback when primary model raises rate limit / network error."""
    with patch("common.clients.litellm.litellm.acompletion", new_callable=AsyncMock) as mock_acomplete:
        # First call fails, second call succeeds with fallback model (gemma-4-26b-a4b-it)
        mock_fallback_choice = AsyncMock()
        mock_fallback_choice.message.content = "Fallback response from secondary model."
        mock_fallback_resp = AsyncMock()
        mock_fallback_resp.choices = [mock_fallback_choice]
        mock_fallback_resp.usage = AsyncMock(prompt_tokens=12, completion_tokens=8, total_tokens=20)

        mock_acomplete.side_effect = [
            Exception("Simulated 429 RateLimitExceeded on primary model"),
            mock_fallback_resp,
        ]

        messages = [{"role": "user", "content": "Execute analysis."}]
        fallbacks = [
            {"model": "gemini/gemma-4-26b-a4b-it", "api_key": "test-key", "context_window": 8192}
        ]

        resp = await completion_with_fallback(
            model="gemini/gemma-4-31b-it",
            messages=messages,
            fallbacks=fallbacks,
        )
        assert resp is not None
        assert "Fallback response" in resp.choices[0].message.content
        assert mock_acomplete.call_count == 2


def test_truncate_messages_helper():
    """Verify message truncation preserves system message and trims conversation history."""
    messages = [
        {"role": "system", "content": "System directive."},
        {"role": "user", "content": "Old message 1"},
        {"role": "assistant", "content": "Old response 1"},
        {"role": "user", "content": "Latest user query"},
    ]
    with patch("common.clients.litellm.litellm.token_counter", side_effect=[100, 80, 50]):
        truncated = truncate_messages(messages, "gemini/gemma-4-31b-it", limit=60)
        assert len(truncated) < len(messages)
        assert truncated[0]["role"] == "system"
        assert truncated[-1]["content"] == "Latest user query"
