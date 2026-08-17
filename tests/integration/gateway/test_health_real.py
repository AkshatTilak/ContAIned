"""Real-world Health Check Integration Tests (B8-16 / sub_16_06).

Tests gateway health probes, service grid statuses, and partial degradation reports.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_gateway_health_checks(gateway_client: AsyncClient):
    """Verify health endpoint reports all services with latency metadata."""
    # 1. Check /health
    resp = await gateway_client.get("/health")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded", "unhealthy")
    assert "services" in data
    services = data["services"]
    assert "gateway" in services
    assert "database" in services
    assert "redis" in services
    assert "qdrant" in services

    # 2. Check /api/health alias
    api_resp = await gateway_client.get("/api/health")
    assert api_resp.status_code == resp.status_code
    api_data = api_resp.json()
    assert api_data["status"] == data["status"]
    assert "latencies_ms" in api_data
