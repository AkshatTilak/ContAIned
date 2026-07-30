"""Unit tests for HubContext dependency and require_hub factory (S6-02b)."""

import pytest
import pytest_asyncio
from fastapi import FastAPI, Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from common.clients.postgres import get_async_db
from common.models.database import Base, Hub, HubMember, User
from gateway.auth.hub_context import (
    HubContext,
    require_hub,
    RequireIngestionHub,
    RequireAgentHub,
)


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        # Seed users
        admin_user = User(
            id="admin-id",
            email="admin@example.com",
            display_name="Admin",
            platform_role="admin",
        )
        member_user = User(
            id="member-id",
            email="member@example.com",
            display_name="Member",
            platform_role="member",
        )
        outsider_user = User(
            id="outsider-id",
            email="outsider@example.com",
            display_name="Outsider",
            platform_role="member",
        )
        session.add_all([admin_user, member_user, outsider_user])
        await session.commit()

        # Seed hubs
        ingest_hub = Hub(
            id="hub-ingest-1",
            slug="docs-kb",
            name="Docs KB",
            hub_type="ingestion",
            owner_id="admin-id",
        )
        agent_hub = Hub(
            id="hub-agent-1",
            slug="support-agent",
            name="Support Agent",
            hub_type="agent",
            owner_id="admin-id",
            is_archived=True,
        )
        session.add_all([ingest_hub, agent_hub])
        await session.commit()

        # Seed memberships
        m1 = HubMember(hub_id="hub-ingest-1", user_id="member-id", hub_role="viewer")
        m2 = HubMember(hub_id="hub-agent-1", user_id="member-id", hub_role="contributor")
        session.add_all([m1, m2])
        await session.commit()

        yield session

    await engine.dispose()


def build_test_app(session: AsyncSession):
    app = FastAPI()

    # Override DB dependency
    async def _get_db_override():
        yield session

    app.dependency_overrides[get_async_db] = _get_db_override

    # Simulated auth middleware injecting active test user into request.state.user
    @app.middleware("http")
    async def inject_user_middleware(request: Request, call_next):
        user_header = request.headers.get("X-Test-User", "member-id")
        if user_header == "admin":
            request.state.user = {"sub": "admin-id", "email": "admin@example.com", "platform_role": "admin"}
        elif user_header == "outsider":
            request.state.user = {"sub": "outsider-id", "email": "outsider@example.com", "platform_role": "member"}
        else:
            request.state.user = {"sub": "member-id", "email": "member@example.com", "platform_role": "member"}
        return await call_next(request)

    @app.get("/hubs/{hub_id}/general")
    async def general_hub_route(ctx: HubContext = Depends(require_hub())):
        return {"hub_id": ctx.hub_id, "hub_role": ctx.hub_role}

    @app.get("/hubs/{hub_id}/ingest-viewer")
    async def ingest_viewer_route(ctx: HubContext = RequireIngestionHub("viewer")):
        return {"hub_id": ctx.hub_id, "hub_role": ctx.hub_role}

    @app.post("/hubs/{hub_id}/ingest-contributor")
    async def ingest_contributor_route(ctx: HubContext = RequireIngestionHub("contributor")):
        return {"hub_id": ctx.hub_id, "hub_role": ctx.hub_role}

    @app.get("/hubs/{hub_id}/agent-viewer")
    async def agent_viewer_route(ctx: HubContext = RequireAgentHub("viewer")):
        return {"hub_id": ctx.hub_id, "hub_role": ctx.hub_role}

    @app.post("/hubs/{hub_id}/agent-mutating")
    async def agent_mutating_route(ctx: HubContext = RequireAgentHub("contributor")):
        return {"hub_id": ctx.hub_id, "hub_role": ctx.hub_role}

    @app.post("/hubs/{hub_id}/agent-unarchive")
    async def agent_unarchive_route(ctx: HubContext = Depends(require_hub(hub_type="agent", min_role="owner", allow_archived=True))):
        return {"hub_id": ctx.hub_id, "hub_role": ctx.hub_role}

    return app


@pytest.mark.asyncio
async def test_non_existent_hub_404(async_session: AsyncSession):
    app = build_test_app(async_session)
    client = TestClient(app)

    resp = client.get("/hubs/non-existent-hub-id/general")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Hub not found"}


@pytest.mark.asyncio
async def test_non_member_hub_404_anti_enumeration(async_session: AsyncSession):
    """Outsider gets 404 with byte-identical detail message to non-existent hub."""
    app = build_test_app(async_session)
    client = TestClient(app)

    resp = client.get("/hubs/hub-ingest-1/general", headers={"X-Test-User": "outsider"})
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Hub not found"}


@pytest.mark.asyncio
async def test_insufficient_role_403(async_session: AsyncSession):
    """Member with viewer role requesting contributor route receives 403."""
    app = build_test_app(async_session)
    client = TestClient(app)

    # Member is viewer on hub-ingest-1
    resp = client.post("/hubs/hub-ingest-1/ingest-contributor")
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Insufficient hub role"}


@pytest.mark.asyncio
async def test_hub_type_mismatch_404(async_session: AsyncSession):
    """Calling agent route with ingestion hub_id returns 404."""
    app = build_test_app(async_session)
    client = TestClient(app)

    resp = client.get("/hubs/hub-ingest-1/agent-viewer")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Hub not found"}


@pytest.mark.asyncio
async def test_archived_hub_mutating_409(async_session: AsyncSession):
    """Mutating request against archived hub returns 409, GET succeeds."""
    app = build_test_app(async_session)
    client = TestClient(app)

    # hub-agent-1 is archived
    get_resp = client.get("/hubs/hub-agent-1/agent-viewer")
    assert get_resp.status_code == 200

    post_resp = client.post("/hubs/hub-agent-1/agent-mutating")
    assert post_resp.status_code == 409
    assert post_resp.json() == {"detail": "Hub is archived"}

    # allow_archived=True route succeeds
    unarchive_resp = client.post("/hubs/hub-agent-1/agent-unarchive", headers={"X-Test-User": "admin"})
    assert unarchive_resp.status_code == 200


@pytest.mark.asyncio
async def test_platform_admin_bypass(async_session: AsyncSession):
    """Platform admin passes all checks with effective owner role."""
    app = build_test_app(async_session)
    client = TestClient(app)

    resp = client.post("/hubs/hub-ingest-1/ingest-contributor", headers={"X-Test-User": "admin"})
    assert resp.status_code == 200
    assert resp.json()["hub_role"] == "owner"


def test_invalid_factory_arguments():
    """require_hub raises ValueError at setup time for unknown hub_type or min_role."""
    with pytest.raises(ValueError):
        require_hub(hub_type="invalid_type")

    with pytest.raises(ValueError):
        require_hub(min_role="invalid_role")
