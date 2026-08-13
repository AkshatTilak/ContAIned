
import pytest
pytestmark = pytest.mark.unit
"""Unit and Integration tests for Base Task 3: UI Cleanup, Empty States & Non-Core Dependencies.

Tests:
1. Verify system health response format contains all services required for non-core UI cards.
2. Verify active projects and platform metadata needed for workspace views.
"""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from common.config.settings import get_settings
from gateway.api.health import router as health_router

app = FastAPI()
app.include_router(health_router)

client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_auth(monkeypatch):
    monkeypatch.setattr(get_settings(), "AUTH_ENABLED", False)


def test_system_health_non_core_keys():
    """Verify health response contains all core and non-core service status keys."""
    resp = client.get("/health")
    assert resp.status_code in (status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE)
    data = resp.json()
    assert "status" in data
    assert "services" in data
    services = data["services"]
    assert "database" in services
    assert "redis" in services
    assert "neo4j" in services
    assert "qdrant" in services
    assert "kafka" in services
    assert "inference_server" in services
