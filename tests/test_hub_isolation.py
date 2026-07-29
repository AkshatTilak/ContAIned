"""Hub Isolation & Cross-Tenant Boundary Tests (S6-02e)."""

import pytest
import pytest_asyncio
from fastapi import FastAPI, Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.clients.postgres import get_async_db
from common.models.database import (
    AgentDefinition,
    Base,
    DatastoreBinding,
    Hub,
    HubMember,
    User,
    WorkflowDefinition,
)
from gateway.auth.hub_context import HubContext, require_hub, RequireIngestionHub, RequireAgentHub, RequireWorkflowHub


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
        ua = User(id="user-a", email="usera@example.com", platform_role="member", status="active")
        ub = User(id="user-b", email="userb@example.com", platform_role="member", status="active")
        session.add_all([ua, ub])
        await session.commit()

        # Seed hubs
        ha = Hub(id="hub-a", slug="hub-a-ingest", name="Hub A Ingest", hub_type="ingestion", owner_id="user-a")
        hb = Hub(id="hub-b", slug="hub-b-ingest", name="Hub B Ingest", hub_type="ingestion", owner_id="user-b")
        session.add_all([ha, hb])
        await session.commit()

        # Memberships
        ma = HubMember(hub_id="hub-a", user_id="user-a", hub_role="owner")
        mb = HubMember(hub_id="hub-b", user_id="user-b", hub_role="owner")
        session.add_all([ma, mb])
        await session.commit()

        # Resources
        dsa = DatastoreBinding(id="ds-a", hub_id="hub-a", name="store-a", store_type="qdrant", connection_uri="http://q1")
        dsb = DatastoreBinding(id="ds-b", hub_id="hub-b", name="store-b", store_type="qdrant", connection_uri="http://q2")
        session.add_all([dsa, dsb])
        await session.commit()

        yield session

    await engine.dispose()


def build_isolation_app(session: AsyncSession):
    app = FastAPI()

    async def _get_db_override():
        yield session

    app.dependency_overrides[get_async_db] = _get_db_override

    @app.middleware("http")
    async def inject_user_middleware(request: Request, call_next):
        hdr = request.headers.get("X-Test-User", "user-a")
        if hdr == "user-b":
            request.state.user = {"sub": "user-b", "email": "userb@example.com", "platform_role": "member"}
        else:
            request.state.user = {"sub": "user-a", "email": "usera@example.com", "platform_role": "member"}
        return await call_next(request)

    @app.get("/hubs/{hub_id}/collections/{binding_id}")
    async def get_collection_route(binding_id: str, ctx: HubContext = RequireIngestionHub("viewer")):
        # Ensure collection belongs to hub_id
        if binding_id == "ds-a" and ctx.hub_id == "hub-a":
            return {"id": "ds-a", "hub_id": ctx.hub_id}
        if binding_id == "ds-b" and ctx.hub_id == "hub-b":
            return {"id": "ds-b", "hub_id": ctx.hub_id}
        from fastapi import HTTPException
        raise HTTPException(404, detail="Hub not found")

    return app


@pytest.mark.asyncio
async def test_hub_isolation_positive_and_negative_controls(async_session: AsyncSession):
    app = build_isolation_app(async_session)
    client = TestClient(app)

    # 1. Positive control: User A on Hub A with Resource A -> 200
    r1 = client.get("/hubs/hub-a/collections/ds-a", headers={"X-Test-User": "user-a"})
    assert r1.status_code == 200
    assert r1.json()["id"] == "ds-a"

    # 2. Foreign resource ID under own hub -> 404
    r2 = client.get("/hubs/hub-a/collections/ds-b", headers={"X-Test-User": "user-a"})
    assert r2.status_code == 404
    assert r2.json() == {"detail": "Hub not found"}

    # 3. User A requesting Hub B (unmember) -> 404 (anti-enumeration)
    r3 = client.get("/hubs/hub-b/collections/ds-b", headers={"X-Test-User": "user-a"})
    assert r3.status_code == 404
    assert r3.json() == {"detail": "Hub not found"}

    # 4. Assert body 2 and body 3 are byte-identical
    assert r2.json() == r3.json()
