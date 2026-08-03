"""Integration tests for S6-06e: Workflow Hub REST API Routes."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.models.database import (
    Base,
    Hub,
    User,
)
from common.config.settings import get_settings
from gateway.main import app
from common.clients.postgres import get_async_db


@pytest.fixture(autouse=True)
def disable_auth(monkeypatch):
    monkeypatch.setattr(get_settings(), "AUTH_ENABLED", False)


@pytest_asyncio.fixture
async def test_db():
    """In-memory SQLite database setup fixture for router testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        user = User(id="user-route-1", email="routes@example.com", display_name="Route User")
        hub = Hub(id="hub-route-1", name="Route Hub", slug="route-hub", hub_type="workflow", owner_id="user-route-1")
        session.add_all([user, hub])
        await session.commit()

    async def _get_test_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_async_db] = _get_test_db
    yield session_factory, "hub-route-1"
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_workflow_crud_and_routes(test_db):
    """Test workflow CRUD API endpoints."""
    sf, hub_id = test_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create Workflow
        res_create = await ac.post(
            f"/api/hubs/{hub_id}/workflows",
            json={"name": "API Test Workflow", "slug": "api-test-wf", "description": "Test flow"},
        )
        assert res_create.status_code == 201
        wf_data = res_create.json()
        wf_id = wf_data["id"]
        assert wf_data["name"] == "API Test Workflow"

        # 2. List Workflows
        res_list = await ac.get(f"/api/hubs/{hub_id}/workflows")
        assert res_list.status_code == 200
        items = res_list.json()
        assert len(items) == 1

        # 3. Get Workflow
        res_get = await ac.get(f"/api/hubs/{hub_id}/workflows/{wf_id}")
        assert res_get.status_code == 200
        assert res_get.json()["id"] == wf_id

        # 4. Patch Workflow
        res_patch = await ac.patch(
            f"/api/hubs/{hub_id}/workflows/{wf_id}",
            json={"name": "Updated Flow Name"},
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["name"] == "Updated Flow Name"

        # 5. Get Draft & ETag
        res_draft = await ac.get(f"/api/hubs/{hub_id}/workflows/{wf_id}/draft")
        assert res_draft.status_code == 200
        etag = res_draft.headers.get("ETag")
        assert etag is not None

        # 6. Put Draft
        graph = {
            "nodes": [
                {"id": "n1", "type": "GatherNode", "data": {}},
                {"id": "n2", "type": "FinalMessageNode", "data": {}},
            ],
            "edges": [{"source": "n1", "target": "n2"}],
        }
        res_put = await ac.put(
            f"/api/hubs/{hub_id}/workflows/{wf_id}/draft",
            json=graph,
            headers={"If-Match": etag},
        )
        assert res_put.status_code == 200

        # 7. Publish Workflow
        res_pub = await ac.post(f"/api/hubs/{hub_id}/workflows/{wf_id}/publish")
        assert res_pub.status_code == 200
        assert res_pub.json()["status"] == "published"

        # 8. Attempt PUT /draft without If-Match when published exists -> 428 ETAG_REQUIRED
        res_no_etag = await ac.put(
            f"/api/hubs/{hub_id}/workflows/{wf_id}/draft",
            json=graph,
        )
        assert res_no_etag.status_code == 428

        # 9. Run Workflow (stream=false)
        res_run = await ac.post(
            f"/api/hubs/{hub_id}/workflows/{wf_id}/run",
            json={"input": {"query": "hello"}, "stream": False},
        )
        assert res_run.status_code == 202
        assert "run_id" in res_run.json()

        # 10. Export Workflow
        res_export = await ac.get(f"/api/hubs/{hub_id}/workflows/{wf_id}/export")
        assert res_export.status_code == 200
        assert "attachment" in res_export.headers.get("Content-Disposition", "")

        # 11. Delete Workflow
        res_del = await ac.delete(f"/api/hubs/{hub_id}/workflows/{wf_id}")
        assert res_del.status_code == 204

        # 12. Confirm 404
        res_404 = await ac.get(f"/api/hubs/{hub_id}/workflows/{wf_id}")
        assert res_404.status_code == 404
