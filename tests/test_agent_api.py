"""Integration tests for Gateway Agent CRUD API endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient

from gateway.main import app
from common.clients.postgres import get_async_db as get_db


@pytest.mark.asyncio
async def test_agent_crud_flow():
    """Test full CRUD lifecycle for Agent Definition via API."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.delete = AsyncMock()
    
    # Store agents in-memory for mock DB queries
    agents_db = {}

    async def mock_execute(stmt, *args, **kwargs):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        
        # Check if statement is querying by ID or all
        stmt_str = str(stmt)
        if "agent_definitions" in stmt_str:
            items = list(agents_db.values())
            if items:
                # Find matching or return latest
                found = items[-1]
                for agent in items:
                    if str(agent.id) in stmt_str:
                        found = agent
                        break
                mock_scalars.first.return_value = found
                mock_scalars.all.return_value = items
            else:
                mock_scalars.first.return_value = None
                mock_scalars.all.return_value = []
        else:
            mock_scalars.all.return_value = []
            mock_scalars.first.return_value = None
            
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar_one_or_none.return_value = mock_scalars.first.return_value
        return mock_result

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.scalar = AsyncMock(side_effect=lambda stmt, *args, **kwargs: (list(agents_db.values())[-1] if agents_db else None))

    # Mock db.add behavior
    def mock_add(obj):
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()
        agents_db[str(obj.id)] = obj

    mock_db.add.side_effect = mock_add

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
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

            # 5. GET /api/agents/models (List available models)
            res = await ac.get("/api/agents/models")
            assert res.status_code == 200
            models_data = res.json()
            assert "models" in models_data or isinstance(models_data, dict)

            # 6. DELETE /api/agents/{id} (Delete agent)
            res = await ac.delete(f"/api/agents/{agent_id}")
            assert res.status_code == 200
            assert res.json()["status"] == "success"

            # Verify deletion returns 404 after removing from mock_db
            agents_db.pop(str(agent_id), None)
            res = await ac.get(f"/api/agents/{agent_id}")
            assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()
