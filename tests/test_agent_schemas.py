"""Unit tests for Agent CRUD Pydantic schemas and database models."""

import pytest
from datetime import datetime
from pydantic import ValidationError
from common.schemas.agent_types import AgentCreate, AgentUpdate, AgentResponse
from common.models.database import AgentDefinition


def test_agent_create_validation():
    """Test valid and invalid AgentCreate parameters."""
    valid_data = {
        "name": "Search Agent",
        "role": "Retrieval Specialist",
        "system_prompt": "You are a helpful search assistant.",
        "model_id": "gemini/gemini-3.5-flash",
        "tools": ["web_search", "qdrant_vector"],
        "temperature": 0.5,
        "max_tokens": 1024,
    }
    agent = AgentCreate(**valid_data)
    assert agent.name == "Search Agent"
    assert agent.role == "Retrieval Specialist"
    assert agent.temperature == 0.5
    assert agent.max_tokens == 1024
    assert len(agent.tools) == 2


def test_agent_create_invalid_temperature():
    """Test out-of-bounds temperature raises ValidationError."""
    with pytest.raises(ValidationError):
        AgentCreate(
            name="Bad Agent",
            role="Tester",
            system_prompt="Test prompt",
            model_id="gemini",
            temperature=3.5,  # Exceeds max 2.0
        )


def test_agent_update_partial():
    """Test AgentUpdate allows partial field updates."""
    update = AgentUpdate(system_prompt="Updated prompt", temperature=0.2)
    assert update.system_prompt == "Updated prompt"
    assert update.temperature == 0.2
    assert update.name is None
    assert update.model_id is None


def test_agent_response_schema():
    """Test AgentResponse serialization."""
    now = datetime.utcnow()
    res = AgentResponse(
        id="test-agent-123",
        name="Test Agent",
        role="Tester",
        system_prompt="Prompt",
        model_id="gemini",
        tools=["test_tool"],
        temperature=0.7,
        max_tokens=2048,
        created_at=now,
        updated_at=now,
    )
    assert res.id == "test-agent-123"
    assert res.tools == ["test_tool"]


def test_agent_definition_model_attributes():
    """Test SQLAlchemy AgentDefinition model attributes."""
    model = AgentDefinition(
        id="agent-001",
        name="SQL Agent",
        role="Database Specialist",
        system_prompt="Execute queries",
        model_id="groq/llama3",
        tools=["postgres_query"],
        temperature=0.1,
        max_tokens=4096,
    )
    assert model.id == "agent-001"
    assert model.name == "SQL Agent"
    assert model.__tablename__ == "agent_definitions"
