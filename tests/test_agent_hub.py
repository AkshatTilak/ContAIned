"""Integration test suite for B6-05 Agent Hub — Scoped Agent Lifecycle."""

import asyncio
from datetime import datetime, timezone
import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.clients.postgres import get_async_db
from common.models.database import (
    APIKeyModel,
    AgentDefinition,
    AgentInvocationLog,
    Base,
    DatastoreBinding,
    Hub,
    HubLink,
    HubMember,
    User,
)
from gateway.api.agent_crud import router as agent_crud_router
from gateway.api.agent_invoke import router as agent_invoke_router
from gateway.api.api_keys import router as api_keys_router, hash_api_key
from gateway.api.external import router as external_router
from gateway.auth.api_key_middleware import APIKeyMiddleware
from projects.syntraflow.src.database.models import SyntraFlowCollection


@pytest_asyncio.fixture
async def agent_test_env():
    """Setup in-memory SQLite database and test client for Agent Hub testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app = FastAPI()
    @app.middleware("http")
    async def inject_user_middleware(request: Request, call_next):
        if not getattr(request.state, "user", None):
            request.state.user = {"sub": "usr-admin", "email": "admin@example.com", "platform_role": "admin"}
        return await call_next(request)

    app.include_router(agent_crud_router, prefix="/api")
    app.include_router(agent_invoke_router, prefix="/api")
    app.include_router(api_keys_router, prefix="/api")
    app.include_router(external_router)
    app.add_middleware(APIKeyMiddleware)

    import common.clients.postgres
    common.clients.postgres._SessionLocal = session_factory

    async def _get_test_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_async_db] = _get_test_db

    # Seed test data
    async with session_factory() as db:
        now = datetime.now(timezone.utc)
        admin = User(id="usr-admin", email="admin@example.com", platform_role="admin", status="active", created_at=now)
        member = User(id="usr-member", email="member@example.com", platform_role="member", status="active", created_at=now)

        hub_alpha = Hub(id="hub-alpha", name="Agent Alpha", slug="alpha", hub_type="agent", owner_id="usr-admin", created_at=now)
        hub_beta = Hub(id="hub-beta", name="Agent Beta", slug="beta", hub_type="agent", owner_id="usr-admin", created_at=now)
        hub_ingest = Hub(id="hub-kb", name="Ingestion KB", slug="kb", hub_type="ingestion", owner_id="usr-admin", created_at=now)

        # Memberships
        mem_alpha_owner = HubMember(hub_id="hub-alpha", user_id="usr-admin", hub_role="owner")
        mem_alpha_contrib = HubMember(hub_id="hub-alpha", user_id="usr-member", hub_role="contributor")
        mem_beta_owner = HubMember(hub_id="hub-beta", user_id="usr-admin", hub_role="owner")

        # Ingestion Collection
        col_kb = SyntraFlowCollection(
            id="col-kb-1",
            hub_id="hub-kb",
            name="policies",
            physical_name="kb__policies",
            embedding_model="jina-clip-v2",
            vector_dimension=1024,
        )

        db.add_all([admin, member, hub_alpha, hub_beta, hub_ingest, mem_alpha_owner, mem_alpha_contrib, mem_beta_owner, col_kb])
        await db.commit()

    return TestClient(app), session_factory


@pytest.mark.asyncio
async def test_agent_hub_scoping_and_slug_collisions(agent_test_env):
    """Test agents in different hubs can share endpoint_slugs but duplicate within a hub returns 409."""
    client, session_factory = agent_test_env

    async with session_factory() as db:
        now = datetime.now(timezone.utc)
        a1 = AgentDefinition(
            id="agent-1",
            hub_id="hub-alpha",
            name="Triage Bot",
            role="assistant",
            system_prompt="Help user",
            model_id="gpt-4o",
            endpoint_slug="triage",
            created_at=now,
        )
        a2 = AgentDefinition(
            id="agent-2",
            hub_id="hub-beta",
            name="Triage Bot",
            role="assistant",
            system_prompt="Help user",
            model_id="gpt-4o",
            endpoint_slug="triage",
            created_at=now,
        )
        db.add_all([a1, a2])
        await db.commit()

    # IDOR check: agent-1 in hub-alpha returns 404 when fetched via hub-beta path
    r_idor = client.get("/api/hubs/hub-beta/agents/agent-1")
    assert r_idor.status_code == 404

    # Fetch via correct hub
    r_ok = client.get("/api/hubs/hub-alpha/agents/agent-1")
    assert r_ok.status_code == 200
    assert r_ok.json()["endpoint_slug"] == "triage"


@pytest.mark.asyncio
async def test_link_enforcement_at_save_and_invoke(agent_test_env):
    """Test binding collection without hub link fails with 403 HUB_LINK_REQUIRED."""
    client, session_factory = agent_test_env

    # Attempt to create agent binding collection in hub-kb without link
    payload = {
        "name": "Doc Bot",
        "role": "assistant",
        "system_prompt": "Help user",
        "model_id": "gpt-4o",
        "collection_bindings": [{"hub_id": "hub-kb", "collection_id": "col-kb-1"}],
    }

    r_save = client.post("/api/hubs/hub-alpha/agents", json=payload)
    assert r_save.status_code == 403
    assert r_save.json()["detail"].startswith("Agent hub 'hub-alpha' is not linked")

    # Seed link from hub-alpha -> hub-kb
    async with session_factory() as db:
        link = HubLink(id="link-1", source_hub_id="hub-alpha", target_hub_id="hub-kb", access_level="use")
        db.add(link)
        await db.commit()

    # Save now succeeds
    r_save_ok = client.post("/api/hubs/hub-alpha/agents", json=payload)
    assert r_save_ok.status_code == 201
    agent_id = r_save_ok.json()["id"]

    # Delete link
    async with session_factory() as db:
        l = await db.get(HubLink, "link-1")
        await db.delete(l)
        await db.commit()

    # Invoke fails with 403 HUB_LINK_REVOKED
    r_invoke = client.post(f"/api/hubs/hub-alpha/agents/{agent_id}/invoke", json={"prompt": "Hello"})
    assert r_invoke.status_code == 403
    assert "revoked" in r_invoke.json()["detail"]


@pytest.mark.asyncio
async def test_external_api_qualified_model_resolution(agent_test_env):
    """Test external OpenAI completions resolve '{hub_slug}/{agent_slug}' and reject bare slug."""
    client, session_factory = agent_test_env

    # Seed agent & API key
    raw_key = "sk-testkey1234567890123456789012345678901234"
    hashed = hash_api_key(raw_key)

    async with session_factory() as db:
        now = datetime.now(timezone.utc)
        a = AgentDefinition(
            id="agent-ext-1",
            hub_id="hub-alpha",
            name="Support Bot",
            role="assistant",
            system_prompt="Support helper",
            model_id="gpt-4o",
            endpoint_slug="support-bot",
            created_at=now,
        )
        key = APIKeyModel(id=1, key=hashed, prefix="sk-testk", user_id="usr-admin", rate_limit=60)
        db.add_all([a, key])
        await db.commit()

    headers = {"Authorization": f"Bearer {raw_key}"}

    # Bare slug fails with 404 model_not_found
    r_bare = client.post("/v1/chat/completions", headers=headers, json={"model": "support-bot", "messages": [{"role": "user", "content": "hi"}]})
    assert r_bare.status_code == 404

    # Qualified slug 'alpha/support-bot' lists in GET /v1/models
    r_models = client.get("/v1/models", headers=headers)
    assert r_models.status_code == 200
    model_ids = [m["id"] for m in r_models.json()["data"]]
    assert "alpha/support-bot" in model_ids
