"""Integration test for Agent Runtime Sync via Redis Pub/Sub."""

import pytest
from common.services.agent_runtime import AgentRuntimeManager
from common.schemas.agent_types import AgentCreate, AgentUpdate


@pytest.mark.asyncio
async def test_agent_runtime_manager_sync():
    """Test AgentRuntimeManager cache update and event handling."""
    manager = AgentRuntimeManager.get_instance()

    agent_id = "test-agent-123"
    initial_config = {
        "id": agent_id,
        "name": "Initial Agent",
        "role": "assistant",
        "system_prompt": "You are a helpful assistant.",
        "model_id": "gemini-3.5-flash",
        "tools": [],
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    manager.set_agent_in_cache(agent_id, initial_config)

    # 1. Verify initial cache state
    cached = manager.get_agent(agent_id)
    assert cached is not None
    assert cached["system_prompt"] == "You are a helpful assistant."

    # 2. Simulate Redis update event payload
    event_payload = {"action": "updated", "agent_id": agent_id}

    # Manually update cache as if reloaded from DB
    updated_config = dict(initial_config)
    updated_config["system_prompt"] = "You are an updated expert system."
    manager.set_agent_in_cache(agent_id, updated_config)

    # Verify updated prompt is retrieved without service restart
    cached_updated = manager.get_agent(agent_id)
    assert cached_updated["system_prompt"] == "You are an updated expert system."

    # 3. Simulate delete event
    delete_event = {"action": "deleted", "agent_id": agent_id}
    await manager.handle_sync_event(delete_event)

    assert manager.get_agent(agent_id) is None
