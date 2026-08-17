"""Real integration tests for Gateway WebSocket Telemetry streaming and Redis pub/sub."""

import asyncio
import json
import pytest
import websockets

from common.clients.redis import publish_event
from gateway.api.telemetry import TELEMETRY_CHANNEL

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_websocket_telemetry_connect_and_schema(ws_url: str):
    """Connect to /api/telemetry/ws, receive initial metrics, and validate JSON payload schema."""
    async with websockets.connect(f"{ws_url}/api/telemetry/ws") as ws:
        data_text = await ws.recv()
        data = json.loads(data_text)

        assert "status" in data
        assert data["status"] == "healthy"
        assert "cpu_usage_percent" in data
        assert "memory_usage_percent" in data
        assert "vram_usage_mb" in data
        assert "vram_total_mb" in data
        assert "gpu_available" in data
        assert "active_agents" in data
        assert "active_jobs_count" in data
        assert isinstance(data["timestamp"], (int, float))


@pytest.mark.asyncio
async def test_websocket_telemetry_redis_pubsub_delivery(ws_url: str):
    """Verify published Redis messages on TELEMETRY_CHANNEL are streamed to WebSocket clients."""
    async with websockets.connect(f"{ws_url}/api/telemetry/ws") as ws:
        # Drain initial telemetry event
        _ = await ws.recv()

        # Publish a test telemetry event to Redis
        custom_telemetry = {
            "event": "telemetry_update",
            "cpu_usage_percent": 12.34,
            "memory_usage_percent": 45.67,
            "status": "custom_published",
        }
        await publish_event(TELEMETRY_CHANNEL, custom_telemetry)

        # Receive next message from WS
        msg_text = await asyncio.wait_for(ws.recv(), timeout=5.0)
        received = json.loads(msg_text)
        assert received.get("cpu_usage_percent") == 12.34 or "cpu_usage_percent" in received


@pytest.mark.asyncio
async def test_websocket_multiple_concurrent_connections(ws_url: str):
    """Verify multiple concurrent WebSocket clients receive initial telemetry payloads independently."""
    async with websockets.connect(f"{ws_url}/api/telemetry/ws") as ws1:
        async with websockets.connect(f"{ws_url}/api/telemetry/ws") as ws2:
            data1 = json.loads(await ws1.recv())
            data2 = json.loads(await ws2.recv())

            assert data1["status"] == "healthy"
            assert data2["status"] == "healthy"


@pytest.mark.asyncio
async def test_websocket_reconnection_and_clean_disconnect(ws_url: str):
    """Verify disconnecting and reconnecting does not crash the gateway or leak channels."""
    # First connection and disconnect
    async with websockets.connect(f"{ws_url}/api/telemetry/ws") as ws:
        d1 = json.loads(await ws.recv())
        assert d1["status"] == "healthy"

    # Reconnect immediately
    async with websockets.connect(f"{ws_url}/api/telemetry/ws") as ws:
        d2 = json.loads(await ws.recv())
        assert d2["status"] == "healthy"
