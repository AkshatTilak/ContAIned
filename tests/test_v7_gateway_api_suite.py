"""Comprehensive Gateway API Integration Test Suite (v7).

Covers Gateway endpoints end-to-end using an in-memory SQLite database and
FastAPI TestClient. External services (Qdrant, Neo4j, inference, MCP, proxy
backends) are mocked so the suite runs without containers.
"""

from __future__ import annotations

import asyncio
import importlib
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# DB / App imports (keep at top for clarity; actual app import is deferred)
# ---------------------------------------------------------------------------
from common.clients.postgres import get_async_db
from common.config.settings import get_settings
from common.models.database import Base, Hub, HubMember, User, UserIdentity, UserSession
from gateway.api import verify_api_key
from gateway.auth.utils import create_access_token, hash_token

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
PASSWORD = "TestPass123!"

# ---------------------------------------------------------------------------
# Test database engine & session factory
# ---------------------------------------------------------------------------
test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def _create_schema() -> None:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _drop_schema() -> None:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


def override_get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return TestingSessionLocal


# ---------------------------------------------------------------------------
# No-op lifespan to bypass external service startup checks
# ---------------------------------------------------------------------------
@asynccontextmanager
async def _noop_lifespan(app) -> AsyncGenerator[None, None]:
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def unique_email(prefix: str = "user") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:8]}@example.com"


async def seed_user(
    email: str,
    *,
    platform_role: str = "member",
    status: str = "active",
    password_hash: str | None = None,
    user_id: str | None = None,
) -> User:
    """Create a user in the test DB and return the model instance."""
    if user_id is None:
        user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = User(
        id=user_id,
        email=email,
        display_name=f"User {email.split('@')[0]}",
        platform_role=platform_role,
        status=status,
        password_hash=password_hash,
        created_at=now,
        last_login=now if status == "active" else None,
    )
    async with TestingSessionLocal() as db:
        db.add(user)
        await db.commit()
    return user


async def seed_password_identity(user_id: str, email: str) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    identity = UserIdentity(
        id=str(uuid.uuid4()),
        user_id=user_id,
        provider="password",
        provider_id=user_id,
        email=email,
        created_at=now,
    )
    async with TestingSessionLocal() as db:
        db.add(identity)
        await db.commit()


async def seed_session(user_id: str, token: str) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session = UserSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=hash_token(token),
        expires_at=now.replace(year=now.year + 1),
        created_at=now,
    )
    async with TestingSessionLocal() as db:
        db.add(session)
        await db.commit()


async def make_auth_headers(
    email: str,
    platform_role: str = "member",
    user_id: str | None = None,
) -> tuple[str, Dict[str, str]]:
    """Create a user, session, and return (user_id, Authorization headers)."""
    effective_user_id: str | None = user_id
    if effective_user_id is None:
        user = await seed_user(email, platform_role=platform_role, status="active")
        effective_user_id = str(user.id)
    assert effective_user_id is not None
    token = create_access_token(user_id=effective_user_id, email=email, platform_role=platform_role)
    await seed_session(effective_user_id, token)
    return effective_user_id, {"Authorization": f"Bearer {token}"}


async def seed_hub(
    hub_type: str,
    owner_id: str,
    slug: str | None = None,
    name: str | None = None,
) -> Hub:
    if slug is None:
        slug = f"{hub_type}-{uuid.uuid4().hex[:8]}"
    if name is None:
        name = f"Test {hub_type} hub"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    hub = Hub(
        id=str(uuid.uuid4()),
        slug=slug,
        name=name,
        hub_type=hub_type,
        owner_id=owner_id,
        created_at=now,
        updated_at=now,
    )
    async with TestingSessionLocal() as db:
        db.add(hub)
        await db.commit()
        await db.refresh(hub)
    return hub


async def seed_membership(hub_id: str, user_id: str, hub_role: str = "viewer") -> HubMember:
    member = HubMember(
        id=str(uuid.uuid4()),
        hub_id=hub_id,
        user_id=user_id,
        hub_role=hub_role,
        created_at=datetime.now(timezone.utc),
    )
    async with TestingSessionLocal() as db:
        db.add(member)
        await db.commit()
    return member


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client(monkeypatch):
    """Yield a TestClient wired to an in-memory test DB and a no-op lifespan."""
    # Reset rate-limit counters between tests (memory storage is process-wide)
    from common.observability.limiter import limiter
    try:
        limiter.reset()
    except Exception:
        pass

    # Force test settings before importing the app
    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", "testing")
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "ALLOW_MEMBER_HUB_CREATION", True)
    monkeypatch.setattr(settings, "ACTIVE_PROJECTS", ["syntraflow", "guardroute", "evalops"])

    # Reset and create fresh schema
    await _drop_schema()
    await _create_schema()

    # Redirect global sessionmaker to test DB
    from common.clients import postgres as postgres_module
    monkeypatch.setattr(postgres_module, "_engine", test_engine)
    monkeypatch.setattr(postgres_module, "_SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(postgres_module, "get_sessionmaker", override_get_sessionmaker)

    # Patch project-level external service clients before importing main
    _patch_external_services()

    # Import / reload gateway.main with no-op lifespan
    with patch("gateway.core.setup.lifespan", _noop_lifespan):
        from gateway import main as gateway_main
        importlib.reload(gateway_main)
        gateway_main.app.dependency_overrides[get_async_db] = override_get_async_db

        with TestClient(gateway_main.app) as test_client:
            yield test_client

    # Cleanup
    await _drop_schema()


def _patch_external_services() -> None:
    """Mock external service integrations used by gateway routers."""
    # Qdrant / vector client
    qdrant_patches = [
        "projects.syntraflow.src.collections.manager.VectorClient",
        "projects.syntraflow.src.retrieval.VectorClient",
        "projects.syntraflow.src.datastores.binding_manager.VectorClient",
        "common.clients.qdrant.VectorClient",
    ]
    for target in qdrant_patches:
        try:
            patch(target, new=_mock_vector_client()).start()
        except Exception:
            pass

    # Neo4j
    try:
        patch("common.clients.neo4j.get_neo4j_driver", new=MagicMock()).start()
    except Exception:
        pass

    # Inference client
    try:
        patch("common.clients.inference.InferenceClient", new=MagicMock()).start()
    except Exception:
        pass

    # Redis pub/sub
    try:
        patch("common.clients.redis.publish_event", new=AsyncMock()).start()
        patch("common.clients.redis.verify_redis_connection", new=AsyncMock()).start()
    except Exception:
        pass

    # LiteLLM completion fallback (agent invocation / playground / external)
    def _mock_completion(**kwargs):
        resp = MagicMock()
        choice = MagicMock()
        choice.message.content = "mocked agent response"
        resp.choices = [choice]
        resp.usage.prompt_tokens = 5
        resp.usage.completion_tokens = 7
        return resp

    try:
        patch("common.clients.litellm.completion_with_fallback", new=_mock_completion).start()
        patch("gateway.api.agent_invoke.completion_with_fallback", new=_mock_completion).start()
        patch("gateway.api.external.completion_with_fallback", new=AsyncMock(return_value=_mock_completion())).start()
        patch("gateway.api.playground.completion_with_fallback", new=_mock_completion).start()
    except Exception:
        pass

    # MCP client
    try:
        patch("gateway.services.mcp_client.discover_tools", new=AsyncMock(return_value=[])).start()
        patch("gateway.services.mcp_client.check_server_health", new=AsyncMock(return_value=("healthy", 0.1))).start()
        patch("gateway.services.mcp_client.invoke_tool", new=AsyncMock(return_value={"result": "ok"})).start()
    except Exception:
        pass

    # Workflow run execution
    try:
        patch(
            "projects.guardroute.src.workflows.run_service.run_workflow",
            new=AsyncMock(return_value={"run_id": str(uuid.uuid4()), "status": "succeeded"}),
        ).start()
    except Exception:
        pass

    # Eval dispatch runner
    try:
        patch(
            "projects.evalops.src.runner.dispatch.run_eval",
            new=AsyncMock(return_value={"run_id": str(uuid.uuid4()), "status": "completed"}),
        ).start()
    except Exception:
        pass

    # Proxy httpx client
    try:
        patch("gateway.api.proxy.httpx.AsyncClient.request", new=AsyncMock()).start()
    except Exception:
        pass


def _mock_vector_client() -> MagicMock:
    client = MagicMock()
    client.verify_connection = AsyncMock(return_value=True)
    client.get_client = MagicMock(return_value=client)
    client.create_collection = MagicMock(return_value=True)
    client.delete_collection = MagicMock(return_value=True)
    client.collection_exists = MagicMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
def test_auth_register_login_logout_me(client):
    email = unique_email("auth")

    # Register
    r = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert r.status_code == 202

    # Approve the user manually in DB (register already created the identity)
    async def _approve():
        async with TestingSessionLocal() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            user.status = "active"
            user.platform_role = "member"
            await db.commit()

    asyncio.run(_approve())

    # Login
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["user"]["email"] == email
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    # Me
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == email

    # Logout
    r = client.post("/auth/logout", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "logged_out"

    # Me after logout should be 401
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Admin user lifecycle
# ---------------------------------------------------------------------------
def test_admin_user_lifecycle(client):
    asyncio.run(_admin_user_lifecycle(client))


async def _admin_user_lifecycle(client):
    admin_email = unique_email("admin")
    admin_id, admin_headers = await make_auth_headers(admin_email, platform_role="admin")

    # Create pending user
    pending_email = unique_email("pending")
    pending_user = await seed_user(pending_email, platform_role="member", status="pending")

    # List users
    r = client.get("/admin/users", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 2

    # Pending users
    r = client.get("/admin/users/pending", headers=admin_headers)
    assert r.status_code == 200
    assert any(u["email"] == pending_email for u in r.json()["items"])

    # Approve
    r = client.post(f"/admin/users/{pending_user.id}/approve", json={"platform_role": "member"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    # Suspend
    r = client.post(f"/admin/users/{pending_user.id}/suspend", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "suspended"

    # Reject attempt on suspended user -> conflict or still suspended
    r = client.post(f"/admin/users/{pending_user.id}/reject", json={"reason": "spam"}, headers=admin_headers)
    assert r.status_code in (200, 409)

    # Detail
    r = client.get(f"/admin/users/{pending_user.id}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["id"] == pending_user.id

    # Non-admin blocked
    member_email = unique_email("member")
    _, member_headers = await make_auth_headers(member_email, platform_role="member")
    r = client.get("/admin/users", headers=member_headers)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Hub management
# ---------------------------------------------------------------------------
def test_hub_crud_members_links(client):
    asyncio.run(_hub_crud_members_links(client))


async def _hub_crud_members_links(client):
    owner_email = unique_email("owner")
    owner_id, owner_headers = await make_auth_headers(owner_email, platform_role="member")

    # Create ingestion hub
    payload = {"slug": f"kb-{uuid.uuid4().hex[:8]}", "name": "KB", "hub_type": "ingestion"}
    r = client.post("/api/hubs", json=payload, headers=owner_headers)
    assert r.status_code == 201
    hub_id = r.json()["id"]

    # List hubs
    r = client.get("/api/hubs", headers=owner_headers)
    assert r.status_code == 200
    assert any(h["id"] == hub_id for h in r.json())

    # Get hub
    r = client.get(f"/api/hubs/{hub_id}", headers=owner_headers)
    assert r.status_code == 200
    assert r.json()["hub"]["id"] == hub_id

    # Update hub
    r = client.patch(f"/api/hubs/{hub_id}", json={"name": "Updated KB"}, headers=owner_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Updated KB"

    # Add member
    member_email = unique_email("member")
    member_id, _ = await make_auth_headers(member_email, platform_role="member")
    r = client.post(f"/api/hubs/{hub_id}/members", json={"user_id": member_id, "hub_role": "viewer"}, headers=owner_headers)
    assert r.status_code == 201

    # Update member role
    r = client.patch(f"/api/hubs/{hub_id}/members/{member_id}", json={"hub_role": "contributor"}, headers=owner_headers)
    assert r.status_code == 200
    assert r.json()["hub_role"] == "contributor"

    # Create second hub for link target
    agent_payload = {"slug": f"agent-{uuid.uuid4().hex[:8]}", "name": "Agent Hub", "hub_type": "agent"}
    r = client.post("/api/hubs", json=agent_payload, headers=owner_headers)
    assert r.status_code == 201
    agent_hub_id = r.json()["id"]

    # Create link (agent -> ingestion)
    r = client.post(f"/api/hubs/{agent_hub_id}/links", json={"target_hub_id": hub_id, "access_level": "read"}, headers=owner_headers)
    assert r.status_code == 201
    link_id = r.json()["id"]

    # List links
    r = client.get(f"/api/hubs/{agent_hub_id}/links", headers=owner_headers)
    assert r.status_code == 200
    assert any(link["id"] == link_id for link in r.json())

    # Archive hub
    r = client.post(f"/api/hubs/{agent_hub_id}/archive", headers=owner_headers)
    assert r.status_code == 200
    assert r.json()["is_archived"] is True

    # Mutating on archived hub -> 409
    r = client.patch(f"/api/hubs/{agent_hub_id}", json={"name": "X"}, headers=owner_headers)
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------
def test_api_key_lifecycle(client):
    asyncio.run(_api_key_lifecycle(client))


async def _api_key_lifecycle(client):
    admin_email = unique_email("admin")
    _, admin_headers = await make_auth_headers(admin_email, platform_role="admin")

    r = client.post("/api/settings/api-keys", json={"name": "integration-key", "rate_limit": 120}, headers=admin_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["raw_key"].startswith("sk-")
    key_id = data["id"]
    raw_key = data["raw_key"]

    # List keys
    r = client.get("/api/settings/api-keys", headers=admin_headers)
    assert r.status_code == 200
    assert any(k["id"] == key_id for k in r.json())

    # Use key to access API
    r = client.get("/api/hubs", headers={"X-API-Key": raw_key})
    assert r.status_code == 200

    # Revoke
    r = client.delete(f"/api/settings/api-keys/{key_id}", headers=admin_headers)
    assert r.status_code == 204

    # Key no longer works
    r = client.get("/api/hubs", headers={"X-API-Key": raw_key})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Ingestion Hub
# ---------------------------------------------------------------------------
def test_ingestion_hub_datastores_and_collections(client):
    asyncio.run(_ingestion_hub_datastores_and_collections(client))


async def _ingestion_hub_datastores_and_collections(client):
    owner_email = unique_email("owner")
    owner_id, owner_headers = await make_auth_headers(owner_email, platform_role="member")

    # Create ingestion hub
    slug = f"kb-{uuid.uuid4().hex[:8]}"
    r = client.post("/api/hubs", json={"slug": slug, "name": "KB", "hub_type": "ingestion"}, headers=owner_headers)
    assert r.status_code == 201
    hub_id = r.json()["id"]

    # Create datastore binding
    r = client.post(
        f"/api/hubs/{hub_id}/ingestion/datastores",
        json={
            "name": "qdrant-main",
            "store_type": "qdrant",
            "connection_uri": "http://localhost:6333",
            "is_default": True,
            "config": {"timeout": 5},
        },
        headers=owner_headers,
    )
    assert r.status_code == 201
    binding_id = r.json()["id"]

    # List datastores
    r = client.get(f"/api/hubs/{hub_id}/ingestion/datastores", headers=owner_headers)
    assert r.status_code == 200
    assert any(ds["id"] == binding_id for ds in r.json())

    # Create collection
    r = client.post(
        f"/api/hubs/{hub_id}/ingestion/collections",
        json={"name": "policies", "description": "Company policies", "retrieval_config": {"strategy": "hybrid", "top_k": 5}},
        headers=owner_headers,
    )
    assert r.status_code == 201
    collection_id = r.json()["id"]

    # List collections
    r = client.get(f"/api/hubs/{hub_id}/ingestion/collections", headers=owner_headers)
    assert r.status_code == 200
    assert any(c["id"] == collection_id for c in r.json())

    # Delete collection
    r = client.delete(f"/api/hubs/{hub_id}/ingestion/collections/{collection_id}", headers=owner_headers)
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# Agent Hub
# ---------------------------------------------------------------------------
def test_agent_hub_crud_and_invoke(client):
    asyncio.run(_agent_hub_crud_and_invoke(client))


async def _agent_hub_crud_and_invoke(client):
    owner_email = unique_email("owner")
    owner_id, owner_headers = await make_auth_headers(owner_email, platform_role="member")

    # Create agent hub
    r = client.post("/api/hubs", json={"slug": f"agent-{uuid.uuid4().hex[:8]}", "name": "Agent Hub", "hub_type": "agent"}, headers=owner_headers)
    assert r.status_code == 201
    hub_id = r.json()["id"]

    # Create agent
    r = client.post(
        f"/api/hubs/{hub_id}/agents",
        json={
            "name": "Support Bot",
            "role": "support",
            "system_prompt": "You are a helpful support assistant.",
            "model_id": "gpt-4o",
            "temperature": 0.5,
            "max_tokens": 1024,
        },
        headers=owner_headers,
    )
    assert r.status_code == 201
    agent_id = r.json()["id"]

    # List agents
    r = client.get(f"/api/hubs/{hub_id}/agents", headers=owner_headers)
    assert r.status_code == 200
    assert any(a["id"] == agent_id for a in r.json())

    # Get agent
    r = client.get(f"/api/hubs/{hub_id}/agents/{agent_id}", headers=owner_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Support Bot"

    # Update agent
    r = client.put(
        f"/api/hubs/{hub_id}/agents/{agent_id}",
        json={"name": "Support Bot Pro", "temperature": 0.3},
        headers=owner_headers,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Support Bot Pro"

    # Invoke agent (non-streaming)
    r = client.post(
        f"/api/hubs/{hub_id}/agents/{agent_id}/invoke",
        json={"prompt": "Hello!", "stream": False},
        headers=owner_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["agent_id"] == agent_id
    assert "response" in data

    # Delete agent
    r = client.delete(f"/api/hubs/{hub_id}/agents/{agent_id}", headers=owner_headers)
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# Workflow Hub
# ---------------------------------------------------------------------------
def test_workflow_hub_crud(client):
    asyncio.run(_workflow_hub_crud(client))


async def _workflow_hub_crud(client):
    owner_email = unique_email("owner")
    owner_id, owner_headers = await make_auth_headers(owner_email, platform_role="member")

    # Create workflow hub
    r = client.post("/api/hubs", json={"slug": f"wf-{uuid.uuid4().hex[:8]}", "name": "Workflow Hub", "hub_type": "workflow"}, headers=owner_headers)
    assert r.status_code == 201
    hub_id = r.json()["id"]

    # Create workflow
    r = client.post(
        f"/api/hubs/{hub_id}/workflows",
        json={
            "name": "Onboarding Flow",
            "slug": f"onboarding-{uuid.uuid4().hex[:8]}",
            "description": "New user onboarding",
            "graph": {"nodes": [], "edges": []},
        },
        headers=owner_headers,
    )
    assert r.status_code == 201
    wf_id = r.json()["id"]

    # List workflows
    r = client.get(f"/api/hubs/{hub_id}/workflows", headers=owner_headers)
    assert r.status_code == 200
    assert any(w["id"] == wf_id for w in r.json())

    # Get workflow
    r = client.get(f"/api/hubs/{hub_id}/workflows/{wf_id}", headers=owner_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Onboarding Flow"

    # Update draft
    r = client.put(
        f"/api/hubs/{hub_id}/workflows/{wf_id}/draft",
        json={"graph": {"nodes": [{"id": "start"}], "edges": []}, "change_note": "added start node"},
        headers=owner_headers,
    )
    assert r.status_code in (200, 201)

    # List templates
    r = client.get(f"/api/hubs/{hub_id}/workflows/templates", headers=owner_headers)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Eval Hub
# ---------------------------------------------------------------------------
def test_eval_hub_suite_and_cases(client):
    asyncio.run(_eval_hub_suite_and_cases(client))


async def _eval_hub_suite_and_cases(client):
    owner_email = unique_email("owner")
    owner_id, owner_headers = await make_auth_headers(owner_email, platform_role="member")

    # Create agent hub + agent target
    r = client.post("/api/hubs", json={"slug": f"agent-{uuid.uuid4().hex[:8]}", "name": "Target Agent Hub", "hub_type": "agent"}, headers=owner_headers)
    assert r.status_code == 201
    agent_hub_id = r.json()["id"]

    r = client.post(
        f"/api/hubs/{agent_hub_id}/agents",
        json={
            "name": "Eval Target",
            "role": "qa",
            "system_prompt": "You answer questions.",
            "model_id": "gpt-4o",
        },
        headers=owner_headers,
    )
    assert r.status_code == 201
    agent_id = r.json()["id"]

    # Create eval hub
    r = client.post("/api/hubs", json={"slug": f"eval-{uuid.uuid4().hex[:8]}", "name": "Eval Hub", "hub_type": "eval"}, headers=owner_headers)
    assert r.status_code == 201
    eval_hub_id = r.json()["id"]

    # Link eval -> agent
    r = client.post(
        f"/api/hubs/{eval_hub_id}/links",
        json={"target_hub_id": agent_hub_id, "access_level": "read"},
        headers=owner_headers,
    )
    assert r.status_code == 201

    # Create suite
    r = client.post(
        f"/api/hubs/{eval_hub_id}/eval/suites",
        json={
            "name": "QA Suite",
            "description": "Basic QA suite",
            "target": {"type": "agent", "target_hub_id": agent_hub_id, "target_id": agent_id},
        },
        headers=owner_headers,
    )
    assert r.status_code == 201
    suite_id = r.json()["id"]

    # Add test case
    r = client.post(
        f"/api/hubs/{eval_hub_id}/eval/suites/{suite_id}/cases",
        json={
            "input_query": "What is 2+2?",
            "expected_output": "4",
            "node_id": "node-1",
            "assertion_type": "equals",
            "expected_value": "4",
        },
        headers=owner_headers,
    )
    assert r.status_code == 201
    case_id = r.json()["id"]

    # List cases
    r = client.get(f"/api/hubs/{eval_hub_id}/eval/suites/{suite_id}/cases", headers=owner_headers)
    assert r.status_code == 200
    assert any(c["id"] == case_id for c in r.json())

    # Clone suite
    r = client.post(f"/api/hubs/{eval_hub_id}/eval/suites/{suite_id}/clone", headers=owner_headers)
    assert r.status_code == 201
    assert r.json()["id"] != suite_id


# ---------------------------------------------------------------------------
# MCP Manager
# ---------------------------------------------------------------------------
def test_mcp_server_lifecycle(client):
    asyncio.run(_mcp_server_lifecycle(client))


async def _mcp_server_lifecycle(client):
    admin_email = unique_email("admin")
    _, admin_headers = await make_auth_headers(admin_email, platform_role="admin")

    r = client.post(
        "/api/mcp/servers",
        json={"name": f"test-server-{uuid.uuid4().hex[:8]}", "url": "http://localhost:9999/sse", "transport": "sse", "auth_type": "none"},
        headers=admin_headers,
    )
    assert r.status_code == 201
    server_id = r.json()["id"]

    # List servers
    r = client.get("/api/mcp/servers", headers=admin_headers)
    assert r.status_code == 200
    assert any(s["id"] == server_id for s in r.json())

    # Update server
    r = client.put(
        f"/api/mcp/servers/{server_id}",
        json={"url": "http://localhost:9999/v2"},
        headers=admin_headers,
    )
    assert r.status_code == 200

    # Delete server
    r = client.delete(f"/api/mcp/servers/{server_id}", headers=admin_headers)
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# Proxy endpoints
# ---------------------------------------------------------------------------
@patch("gateway.api.proxy.httpx.AsyncClient.request")
def test_qdrant_proxy(mock_request, client):
    # The /api/qdrant routes are mounted under the api router whose
    # verify_api_key dependency would otherwise reject the request.
    # Override it to inject an admin user so the route-level RBAC is still
    # exercised.
    async def _admin_verify(request: Request, x_api_key: str | None = None):
        request.state.user = {
            "sub": "admin-proxy-user",
            "email": "admin-proxy@contained.local",
            "platform_role": "admin",
        }

    client.app.dependency_overrides[verify_api_key] = _admin_verify
    mock_request.return_value = MagicMock(
        status_code=200,
        headers={"content-type": "application/json"},
        json=lambda: {"status": "ok"},
        text='{"status": "ok"}',
        content=b'{"status": "ok"}',
    )

    try:
        r = client.get("/api/qdrant/collections", headers={"Accept": "application/json"})
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
    finally:
        client.app.dependency_overrides.pop(verify_api_key, None)


# ---------------------------------------------------------------------------
# Admin invites
# ---------------------------------------------------------------------------
def test_admin_invite_lifecycle(client):
    asyncio.run(_admin_invite_lifecycle(client))


async def _admin_invite_lifecycle(client):
    admin_email = unique_email("admin")
    _, admin_headers = await make_auth_headers(admin_email, platform_role="admin")

    invite_email = unique_email("invited")
    r = client.post(
        "/admin/invites",
        json={"emails": [invite_email], "platform_role": "member", "ttl_hours": 24},
        headers=admin_headers,
    )
    assert r.status_code == 201
    invites = r.json()
    assert len(invites) == 1
    invite_id = invites[0]["invite_id"]
    assert invite_id

    # List invites
    r = client.get("/admin/invites", headers=admin_headers)
    assert r.status_code == 200
    assert any(inv["id"] == invite_id for inv in r.json()["items"])

    # Revoke invite
    r = client.delete(f"/admin/invites/{invite_id}", headers=admin_headers)
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@patch("gateway.api.health._check_db")
@patch("gateway.api.health._check_redis")
@patch("gateway.api.health._check_qdrant")
@patch("gateway.api.health._check_neo4j")
@patch("gateway.api.health._check_kafka")
@patch("gateway.api.health._check_inference")
def test_health_endpoint(mock_inf, mock_kafka, mock_neo4j, mock_qdrant, mock_redis, mock_db, client):
    mock_db.return_value = ("connected", 1.0)
    mock_redis.return_value = ("connected", 0.5)
    mock_qdrant.return_value = ("connected", 1.2)
    mock_neo4j.return_value = ("connected", 0.8)
    mock_kafka.return_value = ("connected", 0.3)
    mock_inf.return_value = ("connected", 2.0, {})

    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["services"]["database"] == "connected"
