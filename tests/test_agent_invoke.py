"""Unit tests for Agent Invocation, Smart Routing, and Logging Endpoints (S5-02a, S5-02b, S5-02c)."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.api.agent_invoke import router as agent_invoke_router, RouteRequest, AgentInvokeRequest


app = FastAPI()
app.include_router(agent_invoke_router)

client = TestClient(app)


def test_agent_invoke_request_schema():
    """Verify Pydantic schema validation for AgentInvokeRequest."""
    req = AgentInvokeRequest(prompt="Hello agent!")
    assert req.prompt == "Hello agent!"
    assert req.stream is False
    assert req.temperature is None


def test_route_request_schema():
    """Verify RouteRequest model defaults."""
    req = RouteRequest(prompt="Summarize docs")
    assert req.routing_strategy == "auto"
    assert req.agent_id is None
    assert req.model_id is None


@patch("gateway.api.agent_invoke.completion_with_fallback", new_callable=AsyncMock)
def test_route_direct_model(mock_completion):
    """Test routing request directly to a model."""
    mock_completion.return_value = {
        "choices": [{"message": {"content": "Routed completion response"}}],
        "model": "gemini/gemini-3.5-flash",
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }

    response = client.post(
        "/route",
        json={"prompt": "Test prompt", "model_id": "gemini/gemini-3.5-flash"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["route_decision"] == "direct_model"
    assert data["response"] == "Routed completion response"
    assert data["model_used"] == "gemini/gemini-3.5-flash"
