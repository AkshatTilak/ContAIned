"""Unit tests for S5-02d: Agent CRUD Enhancements (is_active, endpoint_slug, toggle, slug invocation)."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.schemas.agent_types import AgentCreate, AgentUpdate, AgentResponse
from gateway.api.agent_crud import router as agent_crud_router, slugify
from gateway.api.agent_invoke import router as agent_invoke_router


app = FastAPI()
app.include_router(agent_crud_router, prefix="/api")
app.include_router(agent_invoke_router, prefix="/api")

client = TestClient(app)


def test_slugify_helper():
    """Verify string slugification rules."""
    assert slugify("Code Reviewer Agent!") == "code-reviewer-agent"
    assert slugify("  My    Agent 123  ") == "my-agent-123"
    assert slugify("!!!") == "agent"


def test_agent_schemas_v5():
    """Verify Pydantic models contain is_active and endpoint_slug fields."""
    req = AgentCreate(
        name="Test Agent",
        role="Tester",
        system_prompt="You test code",
        model_id="gemini/gemini-3.5-flash",
    )
    assert req.is_active is True
    assert req.endpoint_slug is None

    update_req = AgentUpdate(is_active=False, endpoint_slug="custom-slug")
    assert update_req.is_active is False
    assert update_req.endpoint_slug == "custom-slug"


class DummyAgent:
    def __init__(self, id, name, role, system_prompt, model_id, tools=None, temperature=0.7, max_tokens=1000, is_active=True, endpoint_slug="test-agent"):
        self.id = id
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.model_id = model_id
        self.tools = tools or []
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.is_active = is_active
        self.endpoint_slug = endpoint_slug
        self.created_at = None
        self.updated_at = None


@pytest.mark.asyncio
async def test_inactive_agent_invocation_rejection():
    """Verify invoking an inactive agent returns 403 Forbidden."""
    inactive_agent = DummyAgent(
        id="agent-inactive-123",
        name="Inactive Researcher",
        role="Research",
        system_prompt="You search papers",
        model_id="gemini/gemini-3.5-flash",
        is_active=False,
        endpoint_slug="inactive-researcher",
    )

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = inactive_agent
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[AsyncSession] = lambda: mock_db

    response = client.post(
        "/api/agents/inactive-researcher/invoke",
        json={"prompt": "Test prompt"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "inactive" in response.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("gateway.api.agent_invoke.completion_with_fallback", new_callable=AsyncMock)
async def test_slug_based_agent_invocation(mock_completion):
    """Verify invoking an active agent using endpoint_slug works."""
    active_agent = DummyAgent(
        id="agent-active-123",
        name="Active Helper",
        role="Assistant",
        system_prompt="Help the user",
        model_id="gemini/gemini-3.5-flash",
        is_active=True,
        endpoint_slug="active-helper",
    )

    mock_completion.return_value = {
        "choices": [{"message": {"content": "Hello from slug invocation!"}}],
        "model": "gemini/gemini-3.5-flash",
        "usage": {"prompt_tokens": 5, "completion_tokens": 10},
    }

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = active_agent
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[AsyncSession] = lambda: mock_db

    response = client.post(
        "/api/agents/active-helper/invoke",
        json={"prompt": "Hello via slug!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Hello from slug invocation!"
    assert data["status"] == "success"

    app.dependency_overrides.clear()
