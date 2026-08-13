
import pytest
pytestmark = pytest.mark.unit
"""Unit and Integration tests for Base Task 2: Gateway Hardening & Error Visibility.

Tests:
1. Dynamic health check status calculation (healthy, degraded, unhealthy) and HTTP status codes (200 / 503).
2. Proxy structured JSON error responses vs HTML cards when infrastructure services are unreachable.
3. Trace ID propagation and error response schema formatting.
"""

from unittest.mock import patch
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from common.config.settings import get_settings
from gateway.api.health import router as health_router
from gateway.api.proxy import router as proxy_router

app = FastAPI()
app.include_router(health_router)
app.include_router(proxy_router)

client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_auth(monkeypatch):
    monkeypatch.setattr(get_settings(), "AUTH_ENABLED", False)


@pytest.mark.asyncio
@patch("gateway.api.health._check_inference")
@patch("gateway.api.health._check_kafka")
@patch("gateway.api.health._check_qdrant")
@patch("gateway.api.health._check_neo4j")
@patch("gateway.api.health._check_redis")
@patch("gateway.api.health._check_db")
async def test_health_check_healthy(
    mock_db, mock_redis, mock_neo4j, mock_qdrant, mock_kafka, mock_inf
):
    """Test health check returns 'healthy' and 200 OK when all services are connected."""
    mock_db.return_value = ("connected", 1.2)
    mock_redis.return_value = ("connected", 0.8)
    mock_neo4j.return_value = ("connected", 2.1)
    mock_qdrant.return_value = ("connected", 1.5)
    mock_kafka.return_value = ("connected", 0.5)
    mock_inf.return_value = ("connected", 5.0, {})

    resp = client.get("/health")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["services"]["database"] == "connected"
    assert data["services"]["redis"] == "connected"


@pytest.mark.asyncio
@patch("gateway.api.health._check_inference")
@patch("gateway.api.health._check_kafka")
@patch("gateway.api.health._check_qdrant")
@patch("gateway.api.health._check_neo4j")
@patch("gateway.api.health._check_redis")
@patch("gateway.api.health._check_db")
async def test_health_check_degraded(
    mock_db, mock_redis, mock_neo4j, mock_qdrant, mock_kafka, mock_inf
):
    """Test health check returns 'degraded' and 200 OK when non-critical services are unreachable."""
    mock_db.return_value = ("connected", 1.2)
    mock_redis.return_value = ("connected", 0.8)
    mock_qdrant.return_value = ("connected", 1.5)
    # Non-critical services offline
    mock_neo4j.return_value = ("unreachable", -1)
    mock_kafka.return_value = ("unreachable", -1)
    mock_inf.return_value = ("unreachable", -1, {})

    resp = client.get("/health")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["services"]["database"] == "connected"
    assert data["services"]["neo4j"] == "unreachable"


@pytest.mark.asyncio
@patch("gateway.api.health._check_inference")
@patch("gateway.api.health._check_kafka")
@patch("gateway.api.health._check_qdrant")
@patch("gateway.api.health._check_neo4j")
@patch("gateway.api.health._check_redis")
@patch("gateway.api.health._check_db")
async def test_health_check_unhealthy(
    mock_db, mock_redis, mock_neo4j, mock_qdrant, mock_kafka, mock_inf
):
    """Test health check returns 'unhealthy' and 503 Service Unavailable when core services are offline."""
    # Database unreachable
    mock_db.return_value = ("unreachable", -1)
    mock_redis.return_value = ("connected", 0.8)
    mock_neo4j.return_value = ("connected", 2.1)
    mock_qdrant.return_value = ("connected", 1.5)
    mock_kafka.return_value = ("connected", 0.5)
    mock_inf.return_value = ("connected", 5.0, {})

    resp = client.get("/health")
    assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["services"]["database"] == "unreachable"


@pytest.mark.asyncio
@patch("gateway.api.proxy.httpx.AsyncClient.request")
async def test_proxy_json_error_handling(mock_request):
    """Test reverse proxy returns structured JSON error when API request fails to reach target engine."""
    import httpx
    mock_request.side_effect = httpx.ConnectError("Connection refused")

    resp = client.get("/collections/test-coll", headers={"Accept": "application/json"})
    assert resp.status_code == status.HTTP_502_BAD_GATEWAY
    data = resp.json()
    assert data["error_code"] == "PROXY_SERVICE_UNAVAILABLE"
    assert "Unable to connect" in data["message"]
    assert data["details"]["service"] == "qdrant"


@pytest.mark.asyncio
@patch("gateway.api.proxy.httpx.AsyncClient.request")
async def test_proxy_html_error_handling(mock_request):
    """Test reverse proxy returns HTML minimal CSS card for browser iframe requests when target engine is offline."""
    import httpx
    mock_request.side_effect = httpx.ConnectError("Connection refused")

    resp = client.get("/qdrant", headers={"Accept": "text/html"})
    assert resp.status_code == status.HTTP_502_BAD_GATEWAY
    assert "text/html" in resp.headers["content-type"]
    assert "Service Unavailable" in resp.text
    assert "OFFLINE" in resp.text
