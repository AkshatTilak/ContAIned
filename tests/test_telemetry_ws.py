"""Unit tests for Gateway Telemetry WebSocket and SSE endpoints.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from gateway.api.telemetry import collect_system_metrics, sse_telemetry_generator


@pytest.mark.asyncio
async def test_collect_system_metrics():
    metrics = await collect_system_metrics()
    assert "cpu_usage_percent" in metrics
    assert "memory_usage_percent" in metrics
    assert "vram_usage_mb" in metrics
    assert metrics["status"] == "healthy"


@pytest.mark.asyncio
async def test_sse_telemetry_generator():
    with patch("gateway.api.telemetry.get_redis_client", side_effect=Exception("Redis offline")):
        gen = sse_telemetry_generator()
        event = await gen.__anext__()
        assert event["event"] == "telemetry"
        assert "cpu_usage_percent" in event["data"]
        await gen.aclose()
