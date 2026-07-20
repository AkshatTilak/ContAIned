"""Integration tests for Gateway Agent CRUD API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.main import app


@pytest.mark.asyncio
async def test_agent_crud_flow():
    """Test full CRUD lifecycle for Agent Definition via API."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # 1. GET /api/agents (List agents)
        res = await ac.get("/api/agents")
        assert res.status_code == 200
        initial_agents = res.json()
        assert isinstance(initial_agents, list)

        # 2. POST /api/agents (Create agent)
        create_payload = {
            "name": "Integration Test Agent",
            "role": "QA Specialist",
            "system_prompt": "You test system routes.",
            "model_id": "gemini/gemini-3.5-flash",
            "tools": ["web_search"],
            "temperature": 0.3,
            "max_tokens": 1024,
        }
        res = await ac.post("/api/agents", json=create_payload)
        assert res.status_code == 201
        created = res.json()
        agent_id = created["id"]
        assert created["name"] == "Integration Test Agent"
        assert created["role"] == "QA Specialist"

        # 3. GET /api/agents/{id} (Fetch single agent)
        res = await ac.get(f"/api/agents/{agent_id}")
        assert res.status_code == 200
        fetched = res.json()
        assert fetched["id"] == agent_id
        assert fetched["system_prompt"] == "You test system routes."

        # 4. PUT /api/agents/{id} (Update agent)
        update_payload = {
            "name": "Updated Test Agent",
            "temperature": 0.1,
        }
        res = await ac.put(f"/api/agents/{agent_id}", json=update_payload)
        assert res.status_code == 200
        updated = res.json()
        assert updated["name"] == "Updated Test Agent"
        assert updated["temperature"] == 0.1
        assert updated["role"] == "QA Specialist"  # Unchanged

        # 5. GET /api/agents/models (List available models)
        res = await ac.get("/api/agents/models")
        assert res.status_code == 200
        models_data = res.json()
        assert "models" in models_data

        # 6. DELETE /api/agents/{id} (Delete agent)
        res = await ac.delete(f"/api/agents/{agent_id}")
        assert res.status_code == 200
        assert res.json()["status"] == "success"

        # Verify deletion returns 404
        res = await ac.get(f"/api/agents/{agent_id}")
        assert res.status_code == 404
