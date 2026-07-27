"""Unit test for S5-11a: Gateway Reverse Proxy for Infrastructure UIs (Qdrant & Neo4j)."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import httpx

from gateway.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_qdrant_reverse_proxy_strips_framing_headers():
    """Verify Qdrant proxy forwards requests and strips framing headers to allow iframe embedding."""
    mock_response = httpx.Response(
        status_code=200,
        headers={
            "content-type": "text/html",
            "x-frame-options": "SAMEORIGIN",
            "content-security-policy": "frame-ancestors 'none'",
        },
        content=b"<html><head><title>Qdrant Dashboard</title></head><body><h1>Qdrant UI</h1></body></html>"
    )

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        response = client.get("/api/qdrant/dashboard")
        assert response.status_code == 200
        assert "Qdrant UI" in response.text
        # Ensure framing headers were overridden / stripped
        assert response.headers.get("x-frame-options") == "ALLOWALL"


@pytest.mark.asyncio
async def test_neo4j_reverse_proxy_offline_fallback():
    """Verify reverse proxy returns bad gateway HTML when downstream infrastructure is offline."""
    with patch("httpx.AsyncClient.request", side_effect=httpx.ConnectError("Connection refused")):
        response = client.get("/api/neo4j/browser")
        assert response.status_code == 502
        assert "Neo4j Graph Database" in response.text
        assert "Service Unavailable" in response.text
