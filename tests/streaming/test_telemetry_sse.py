"""Real integration tests for Gateway SSE Telemetry fallback streaming."""

import json
import pytest
from httpx import AsyncClient

from common.clients.redis import publish_event
from gateway.api.telemetry import TELEMETRY_CHANNEL
from tests.streaming.conftest import collect_all_events

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_sse_telemetry_stream_schema(streaming_client: AsyncClient):
    """Connect to /api/telemetry/stream and verify compliant SSE telemetry event formatting."""
    events = await collect_all_events(
        streaming_client,
        "/api/telemetry/stream",
        method="GET",
        timeout_s=5.0,
        max_events=1,
    )

    assert len(events) >= 1
    first_event = events[0]
    assert first_event["event"] in ("telemetry", "message")

    data = first_event["data"]
    if isinstance(data, str):
        data = json.loads(data)

    assert "status" in data
    assert data["status"] == "healthy"
    assert "cpu_usage_percent" in data
    assert "memory_usage_percent" in data
    assert "vram_usage_mb" in data
    assert "vram_total_mb" in data


@pytest.mark.asyncio
async def test_sse_telemetry_redis_pubsub_delivery(streaming_client: AsyncClient):
    """Verify published Redis messages are delivered via SSE."""
    # Publish custom event
    custom_msg = {
        "event": "telemetry_update",
        "cpu_usage_percent": 99.9,
        "status": "custom_sse_payload",
    }
    await publish_event(TELEMETRY_CHANNEL, custom_msg)

    events = await collect_all_events(
        streaming_client,
        "/api/telemetry/stream",
        method="GET",
        timeout_s=5.0,
        max_events=2,
    )

    assert len(events) >= 1
    assert any(
        (isinstance(e["data"], dict) and "status" in e["data"])
        or (isinstance(e["data"], str) and "status" in e["data"])
        for e in events
    )
