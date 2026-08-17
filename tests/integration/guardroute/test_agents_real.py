"""Real-world integration test suite for GuardRoute Agent Management against real Postgres.

Covers Agent CRUD, slug auto-generation, update & slug regeneration, active status toggles,
agent duplication, search/filtering, available model discovery, and strict hub scoping.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import AgentDefinition, AuditLog, ModelRegistryModel
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    """Build Authorization header for a seeded user."""
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_agent_with_model_config_and_verify_db(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Create agent with model config and system prompt, verify DB row and audit log."""
    owner = await seed_user(email="agent_creator@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Agent Test Hub", slug="agent-test-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    payload = {
        "name": "Customer Support Agent",
        "role": "support",
        "system_prompt": "You are a polite, helpful customer service agent.",
        "model_id": "gemini/gemma-4-31b-it",
        "tools": ["web_search", "knowledge_base"],
        "temperature": 0.3,
        "max_tokens": 1500,
        "is_active": True,
    }

    resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/agents",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 201, f"Create agent failed: {resp.text}"
    data = resp.json()
    assert data["name"] == "Customer Support Agent"
    assert data["role"] == "support"
    assert data["model_id"] == "gemini/gemma-4-31b-it"
    assert data["endpoint_slug"] == "customer-support-agent"
    assert data["tools"] == ["web_search", "knowledge_base"]
    assert data["temperature"] == 0.3
    assert data["max_tokens"] == 1500
    assert data["is_active"] is True
    assert data["hub_id"] == hub.id
    assert data["hub_slug"] == hub.slug
    agent_id = data["id"]

    # Verify real DB row persistence
    db_agent = await real_db_session.get(AgentDefinition, agent_id)
    assert db_agent is not None
    assert db_agent.name == "Customer Support Agent"
    assert db_agent.hub_id == hub.id
    assert db_agent.endpoint_slug == "customer-support-agent"
    assert db_agent.system_prompt == "You are a polite, helpful customer service agent."
    assert db_agent.model_id == "gemini/gemma-4-31b-it"

    # Verify AuditLog row
    stmt = select(AuditLog).where(
        AuditLog.hub_id == hub.id,
        AuditLog.resource_type == "agent",
        AuditLog.resource_id == agent_id,
        AuditLog.action == "create",
    )
    audit = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert audit is not None
    assert "Customer Support Agent" in (audit.summary or "")


@pytest.mark.asyncio
async def test_update_agent_and_slug_regeneration(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Update agent name and fields, verifying DB update and endpoint slug regeneration."""
    owner = await seed_user(email="agent_updater@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Agent Update Hub", slug="agent-update-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/agents",
        json={
            "name": "Initial Agent",
            "role": "general",
            "system_prompt": "Initial prompt.",
            "model_id": "gemini/gemma-4-26b-a4b-it",
            "temperature": 0.7,
            "max_tokens": 2048,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    agent_id = create_resp.json()["id"]
    assert create_resp.json()["endpoint_slug"] == "initial-agent"

    # Update name, system prompt, temperature without explicit slug -> retains existing slug for URL stability
    update_resp = await gateway_client.put(
        f"/api/hubs/{hub.id}/agents/{agent_id}",
        json={
            "name": "Senior Technical Advisor",
            "system_prompt": "Advanced technical advice.",
            "temperature": 0.2,
            "max_tokens": 4096,
        },
        headers=headers,
    )
    assert update_resp.status_code == 200, f"Update agent failed: {update_resp.text}"
    data = update_resp.json()
    assert data["name"] == "Senior Technical Advisor"
    assert data["endpoint_slug"] == "initial-agent"
    assert data["system_prompt"] == "Advanced technical advice."
    assert data["temperature"] == 0.2
    assert data["max_tokens"] == 4096

    # Update with explicit endpoint_slug -> regenerates/updates endpoint_slug
    update_slug_resp = await gateway_client.put(
        f"/api/hubs/{hub.id}/agents/{agent_id}",
        json={"endpoint_slug": "senior-technical-advisor"},
        headers=headers,
    )
    assert update_slug_resp.status_code == 200
    assert update_slug_resp.json()["endpoint_slug"] == "senior-technical-advisor"

    # Verify persisted in real PostgreSQL
    db_agent = await real_db_session.get(AgentDefinition, agent_id)
    await real_db_session.refresh(db_agent)
    assert db_agent.name == "Senior Technical Advisor"
    assert db_agent.endpoint_slug == "senior-technical-advisor"
    assert db_agent.temperature == 0.2


@pytest.mark.asyncio
async def test_toggle_agent_active_status(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Toggle agent active status between active and inactive."""
    owner = await seed_user(email="agent_toggler@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Agent Toggle Hub", slug="agent-toggle-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/agents",
        json={
            "name": "Toggle Agent",
            "role": "bot",
            "system_prompt": "Prompt",
            "model_id": "gemini/gemma-3-12b-it",
            "is_active": True,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    agent_id = create_resp.json()["id"]
    assert create_resp.json()["is_active"] is True

    # Toggle to Inactive
    toggle_1 = await gateway_client.patch(f"/api/hubs/{hub.id}/agents/{agent_id}/toggle", headers=headers)
    assert toggle_1.status_code == 200
    assert toggle_1.json()["is_active"] is False

    db_agent = await real_db_session.get(AgentDefinition, agent_id)
    await real_db_session.refresh(db_agent)
    assert db_agent.is_active is False

    # Toggle back to Active
    toggle_2 = await gateway_client.patch(f"/api/hubs/{hub.id}/agents/{agent_id}/toggle", headers=headers)
    assert toggle_2.status_code == 200
    assert toggle_2.json()["is_active"] is True

    await real_db_session.refresh(db_agent)
    assert db_agent.is_active is True


@pytest.mark.asyncio
async def test_duplicate_agent_within_hub(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Duplicate an existing agent and verify new name suffix and unique endpoint slug."""
    owner = await seed_user(email="agent_duplicator@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Agent Duplicate Hub", slug="agent-dup-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/agents",
        json={
            "name": "Primary Agent",
            "role": "analyst",
            "system_prompt": "Analyze datasets.",
            "model_id": "gemini/gemma-3-4b-it",
            "temperature": 0.5,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    original_id = create_resp.json()["id"]

    # Duplicate
    dup_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/agents/{original_id}/duplicate",
        headers=headers,
    )
    assert dup_resp.status_code == 201, f"Duplicate agent failed: {dup_resp.text}"
    dup_data = dup_resp.json()
    assert dup_data["id"] != original_id
    assert dup_data["name"] == "Primary Agent (Copy)"
    assert dup_data["role"] == "analyst"
    assert dup_data["system_prompt"] == "Analyze datasets."
    assert dup_data["endpoint_slug"].startswith("primary-agent-copy")

    # Verify both exist in DB
    stmt = select(AgentDefinition).where(AgentDefinition.hub_id == hub.id)
    agents = (await real_db_session.execute(stmt)).scalars().all()
    assert len(agents) == 2


@pytest.mark.asyncio
async def test_delete_agent_and_cleanup(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Delete an agent and verify it is removed from database and returns 404."""
    owner = await seed_user(email="agent_deleter@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Agent Delete Hub", slug="agent-del-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    create_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/agents",
        json={
            "name": "Disposable Agent",
            "role": "temp",
            "system_prompt": "Disposable prompt.",
            "model_id": "gemini/gemma-4-31b-it",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    agent_id = create_resp.json()["id"]

    # Delete
    del_resp = await gateway_client.delete(f"/api/hubs/{hub.id}/agents/{agent_id}", headers=headers)
    assert del_resp.status_code == 204

    # Subsequent GET returns 404
    get_resp = await gateway_client.get(f"/api/hubs/{hub.id}/agents/{agent_id}", headers=headers)
    assert get_resp.status_code == 404

    # Direct DB check
    db_agent = await real_db_session.get(AgentDefinition, agent_id)
    assert db_agent is None


@pytest.mark.asyncio
async def test_agent_hub_scoping_isolation(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Verify an agent in Hub A cannot be accessed or modified from Hub B."""
    user_a = await seed_user(email="hub_a_user@contained.ai", role="member")
    hub_a = await seed_hub(owner=user_a, name="Hub A", slug="hub-a-scoped", hub_type="agent")
    headers_a = await _auth_headers(user_a)

    user_b = await seed_user(email="hub_b_user@contained.ai", role="member")
    hub_b = await seed_hub(owner=user_b, name="Hub B", slug="hub-b-scoped", hub_type="agent")
    headers_b = await _auth_headers(user_b)

    # Create in Hub A
    create_resp = await gateway_client.post(
        f"/api/hubs/{hub_a.id}/agents",
        json={
            "name": "Secret Agent A",
            "role": "secret",
            "system_prompt": "Hub A only",
            "model_id": "gemini/gemma-4-26b-a4b-it",
        },
        headers=headers_a,
    )
    assert create_resp.status_code == 201
    agent_a_id = create_resp.json()["id"]

    # Hub B cannot GET agent A
    get_from_b = await gateway_client.get(f"/api/hubs/{hub_b.id}/agents/{agent_a_id}", headers=headers_b)
    assert get_from_b.status_code == 404

    # Hub B cannot PUT agent A
    put_from_b = await gateway_client.put(
        f"/api/hubs/{hub_b.id}/agents/{agent_a_id}",
        json={"name": "Hijacked Agent"},
        headers=headers_b,
    )
    assert put_from_b.status_code == 404

    # Hub B cannot DELETE agent A
    del_from_b = await gateway_client.delete(f"/api/hubs/{hub_b.id}/agents/{agent_a_id}", headers=headers_b)
    assert del_from_b.status_code == 404

    # Hub B list does not contain agent A
    list_b = await gateway_client.get(f"/api/hubs/{hub_b.id}/agents", headers=headers_b)
    assert list_b.status_code == 200
    assert not any(a["id"] == agent_a_id for a in list_b.json())


@pytest.mark.asyncio
async def test_list_agents_filtering_and_search(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Filter agents by is_active status and query string q."""
    owner = await seed_user(email="agent_filterer@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Agent Filter Hub", slug="agent-filter-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    # Seed 3 agents: 2 active (Search Alpha, Support Beta), 1 inactive (Search Gamma)
    await gateway_client.post(
        f"/api/hubs/{hub.id}/agents",
        json={"name": "Search Alpha", "role": "search", "system_prompt": "P1", "model_id": "m1", "is_active": True},
        headers=headers,
    )
    await gateway_client.post(
        f"/api/hubs/{hub.id}/agents",
        json={"name": "Support Beta", "role": "support", "system_prompt": "P2", "model_id": "m1", "is_active": True},
        headers=headers,
    )
    await gateway_client.post(
        f"/api/hubs/{hub.id}/agents",
        json={"name": "Search Gamma", "role": "search", "system_prompt": "P3", "model_id": "m1", "is_active": False},
        headers=headers,
    )

    # Filter is_active=true
    resp_active = await gateway_client.get(f"/api/hubs/{hub.id}/agents?is_active=true", headers=headers)
    assert resp_active.status_code == 200
    active_names = [a["name"] for a in resp_active.json()]
    assert "Search Alpha" in active_names
    assert "Support Beta" in active_names
    assert "Search Gamma" not in active_names

    # Filter is_active=false
    resp_inactive = await gateway_client.get(f"/api/hubs/{hub.id}/agents?is_active=false", headers=headers)
    assert resp_inactive.status_code == 200
    inactive_names = [a["name"] for a in resp_inactive.json()]
    assert "Search Gamma" in inactive_names
    assert len(inactive_names) == 1

    # Search q=Search
    resp_search = await gateway_client.get(f"/api/hubs/{hub.id}/agents?q=Search", headers=headers)
    assert resp_search.status_code == 200
    search_names = [a["name"] for a in resp_search.json()]
    assert "Search Alpha" in search_names
    assert "Search Gamma" in search_names
    assert "Support Beta" not in search_names


@pytest.mark.asyncio
async def test_available_models_endpoint(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Retrieve available completion & classifier models from Model Registry."""
    owner = await seed_user(email="model_seeker@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Agent Model Hub", slug="agent-model-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    # Seed model registry rows in Postgres
    m1 = ModelRegistryModel(
        role="completion",
        mode="api",
        provider="google",
        model_id="gemini/gemma-4-31b-it",
        display_name="Gemma 4 31B",
        is_enabled=True,
    )
    m2 = ModelRegistryModel(
        role="classifier",
        mode="api",
        provider="google",
        model_id="gemini/gemma-4-26b-a4b-it",
        display_name="Gemma 4 26B A4B",
        is_enabled=True,
    )
    real_db_session.add_all([m1, m2])
    await real_db_session.flush()

    resp = await gateway_client.get(f"/api/hubs/{hub.id}/agents/available-models", headers=headers)
    assert resp.status_code == 200, f"Available models query failed: {resp.text}"
    models = resp.json().get("models", [])
    model_ids = [m["model_id"] for m in models]
    assert "gemini/gemma-4-31b-it" in model_ids
    assert "gemini/gemma-4-26b-a4b-it" in model_ids
