"""Gateway lifecycle regression tests for hub and agent CRUD flows."""

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.clients.postgres import get_async_db
from common.models.database import Base, Hub, HubMember, User
from gateway.api.agent_crud import router as agent_router
from gateway.api.hubs import router as hubs_router


@pytest_asyncio.fixture
async def app_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        user = User(
            id="user-1",
            email="user1@example.com",
            display_name="User One",
            platform_role="member",
            status="active",
        )
        session.add(user)
        await session.commit()
        yield session

    await engine.dispose()


def build_app(session: AsyncSession):
    app = FastAPI()

    async def _get_db_override():
        yield session

    app.dependency_overrides[get_async_db] = _get_db_override

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = {"sub": "user-1", "email": "user1@example.com", "platform_role": "member"}
        return await call_next(request)

    app.include_router(hubs_router, prefix="/api")
    app.include_router(agent_router, prefix="/api")
    return app


@pytest.mark.asyncio
async def test_agent_lifecycle_inside_agent_hub(app_session: AsyncSession):
    app = build_app(app_session)
    client = TestClient(app)

    hub_resp = client.post(
        "/api/hubs",
        json={"slug": "agent-lifecycle-hub", "name": "Agent Lifecycle Hub", "hub_type": "agent"},
    )
    assert hub_resp.status_code == 201
    hub_id = hub_resp.json()["id"]

    list_resp = client.get(f"/api/hubs/{hub_id}/agents")
    assert list_resp.status_code == 200
    assert list_resp.json() == []

    create_resp = client.post(
        f"/api/hubs/{hub_id}/agents",
        json={
            "name": "Lifecycle Agent",
            "role": "support",
            "system_prompt": "You help with lifecycle verification.",
            "model_id": "gpt-test",
            "temperature": 0.2,
            "max_tokens": 512,
        },
    )
    assert create_resp.status_code == 201
    agent_id = create_resp.json()["id"]
    assert create_resp.json()["endpoint_slug"] == "lifecycle-agent"

    get_resp = client.get(f"/api/hubs/{hub_id}/agents/{agent_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Lifecycle Agent"

    delete_resp = client.delete(f"/api/hubs/{hub_id}/agents/{agent_id}")
    assert delete_resp.status_code == 204

    remaining_resp = client.get(f"/api/hubs/{hub_id}/agents")
    assert remaining_resp.status_code == 200
    assert remaining_resp.json() == []
