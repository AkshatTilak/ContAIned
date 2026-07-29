"""Unit tests for Hub, Membership, and Link API routes (S6-02d)."""

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.clients.postgres import get_async_db
from common.models.database import (
    AuditLog,
    Base,
    DatastoreBinding,
    Hub,
    HubLink,
    HubMember,
    User,
)
from gateway.api.hubs import router as hubs_router


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
            id="user-admin",
            email="admin@example.com",
            display_name="Admin",
            platform_role="admin",
            status="active",
        )
        member1 = User(
            id="user-1",
            email="user1@example.com",
            display_name="User One",
            platform_role="member",
            status="active",
        )

        member2 = User(
            id="user-2",
            email="user2@example.com",
            display_name="User Two",
            platform_role="member",
            status="active",
        )

        session.add_all([admin_user, member1, member2])
        await session.commit()

        yield session

    await engine.dispose()


def build_api_test_app(session: AsyncSession):
    app = FastAPI()

    async def _get_db_override():
        yield session

    app.dependency_overrides[get_async_db] = _get_db_override

    @app.middleware("http")
    async def inject_user_middleware(request: Request, call_next):
        user_hdr = request.headers.get("X-Test-User", "user-1")
        if user_hdr == "admin":
            request.state.user = {"sub": "user-admin", "email": "admin@example.com", "platform_role": "admin"}
        elif user_hdr == "user-2":
            request.state.user = {"sub": "user-2", "email": "user2@example.com", "platform_role": "member"}
        else:
            request.state.user = {"sub": "user-1", "email": "user1@example.com", "platform_role": "member"}
        return await call_next(request)

    app.include_router(hubs_router, prefix="/api")
    return app


@pytest.mark.asyncio
async def test_create_hub_and_list(async_session: AsyncSession):
    """Creating a hub sets creator as owner; listing returns only caller's hubs."""
    app = build_api_test_app(async_session)
    client = TestClient(app)

    payload = {
        "slug": "kb-main",
        "name": "KB Main",
        "hub_type": "ingestion",
        "description": "Main Knowledge Base",
    }
    resp = client.post("/api/hubs", json=payload, headers={"X-Test-User": "user-1"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "kb-main"
    assert data["owner_id"] == "user-1"

    # User 1 sees the hub
    list_resp = client.get("/api/hubs", headers={"X-Test-User": "user-1"})
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # User 2 sees zero hubs
    list_resp2 = client.get("/api/hubs", headers={"X-Test-User": "user-2"})
    assert list_resp2.status_code == 200
    assert len(list_resp2.json()) == 0


@pytest.mark.asyncio
async def test_duplicate_slug_conflict(async_session: AsyncSession):
    """Duplicate (hub_type, slug) returns 409 HUB_SLUG_TAKEN; different hub_type succeeds."""
    app = build_api_test_app(async_session)
    client = TestClient(app)

    p1 = {"slug": "shared-slug", "name": "Ingest Shared", "hub_type": "ingestion"}
    r1 = client.post("/api/hubs", json=p1, headers={"X-Test-User": "user-1"})
    assert r1.status_code == 201

    # Duplicate same hub_type -> 409
    r2 = client.post("/api/hubs", json=p1, headers={"X-Test-User": "user-1"})
    assert r2.status_code == 409

    # Same slug, different hub_type -> 201
    p2 = {"slug": "shared-slug", "name": "Agent Shared", "hub_type": "agent"}
    r3 = client.post("/api/hubs", json=p2, headers={"X-Test-User": "user-1"})
    assert r3.status_code == 201


@pytest.mark.asyncio
async def test_last_owner_protection_and_transfer(async_session: AsyncSession):
    """Removing/demoting the sole owner fails with 409 LAST_OWNER; succeeds after transfer."""
    app = build_api_test_app(async_session)
    client = TestClient(app)

    # User 1 creates hub
    create_res = client.post("/api/hubs", json={"slug": "h1", "name": "H1", "hub_type": "agent"}, headers={"X-Test-User": "user-1"})
    hub_id = create_res.json()["id"]

    # Attempt to demote sole owner -> 409
    demote_res = client.patch(f"/api/hubs/{hub_id}/members/user-1", json={"hub_role": "maintainer"}, headers={"X-Test-User": "user-1"})
    assert demote_res.status_code == 409
    assert demote_res.headers.get("X-Error-Code") == "LAST_OWNER"

    # Transfer ownership to User 2
    transfer_res = client.post(f"/api/hubs/{hub_id}/transfer-ownership", json={"new_owner_user_id": "user-2"}, headers={"X-Test-User": "user-1"})
    assert transfer_res.status_code == 200
    assert transfer_res.json()["owner_id"] == "user-2"


@pytest.mark.asyncio
async def test_delete_non_empty_hub_409(async_session: AsyncSession):
    """Deleting non-empty hub returns 409 HUB_NOT_EMPTY."""
    app = build_api_test_app(async_session)
    client = TestClient(app)

    c_res = client.post("/api/hubs", json={"slug": "ingest-empty", "name": "Ingest Empty", "hub_type": "ingestion"}, headers={"X-Test-User": "user-1"})
    hub_id = c_res.json()["id"]

    # Add a datastore binding
    ds = DatastoreBinding(id="ds-test", hub_id=hub_id, name="qdrant", store_type="qdrant", connection_uri="http://qdrant:6333")
    async_session.add(ds)
    await async_session.commit()

    del_res = client.delete(f"/api/hubs/{hub_id}", headers={"X-Test-User": "user-1"})
    assert del_res.status_code == 409
    assert del_res.headers.get("X-Error-Code") == "HUB_NOT_EMPTY"

    # Delete datastore binding and retry
    await async_session.delete(ds)
    await async_session.commit()

    del_res2 = client.delete(f"/api/hubs/{hub_id}", headers={"X-Test-User": "user-1"})
    assert del_res2.status_code == 204


@pytest.mark.asyncio
async def test_link_management(async_session: AsyncSession):
    """Test link creation, link direction 422, link deletion, and audit logging."""
    app = build_api_test_app(async_session)
    client = TestClient(app)

    # User 1 creates Agent Hub & Ingestion Hub
    h_agent = client.post("/api/hubs", json={"slug": "agent-hub", "name": "Agent Hub", "hub_type": "agent"}, headers={"X-Test-User": "user-1"}).json()
    h_ingest = client.post("/api/hubs", json={"slug": "ingest-hub", "name": "Ingest Hub", "hub_type": "ingestion"}, headers={"X-Test-User": "user-1"}).json()

    # Disallowed link direction (ingestion -> agent) -> 422
    invalid_link = client.post(f"/api/hubs/{h_ingest['id']}/links", json={"target_hub_id": h_agent["id"], "access_level": "read"}, headers={"X-Test-User": "user-1"})
    assert invalid_link.status_code == 422

    # Valid link direction (agent -> ingestion) -> 201
    valid_link = client.post(f"/api/hubs/{h_agent['id']}/links", json={"target_hub_id": h_ingest["id"], "access_level": "read"}, headers={"X-Test-User": "user-1"})
    assert valid_link.status_code == 201
    link_id = valid_link.json()["id"]

    # Delete link -> 204
    del_link = client.delete(f"/api/hubs/{h_agent['id']}/links/{link_id}", headers={"X-Test-User": "user-1"})
    assert del_link.status_code == 204

    # Verify audit log rows were generated
    logs = (await async_session.execute(select(AuditLog))).scalars().all()
    assert len(logs) >= 4
