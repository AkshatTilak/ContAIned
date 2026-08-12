"""Backend API tests for Base Task 13: Workflow Canvas UX Fixes (v7).

Covers the draft persistence endpoints (PUT/GET /{wf_id}/draft) and the
cross-hub links direction endpoint (GET /{hub_id}/links?direction=incoming|outgoing).

Uses the same in-memory SQLite + ASGITransport fixture pattern as
``tests/test_workflow_routes.py``.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.models.database import (
    Base,
    Hub,
    HubLink,
    HubMember,
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
        user = User(id="user-canvas-1", email="canvas@example.com", display_name="Canvas User")

        # Workflow hub (the hub under test)
        wf_hub = Hub(id="hub-wf-1", name="Workflow Hub", slug="wf-hub", hub_type="workflow", owner_id="user-canvas-1")
        # Agent hub (linked target)
        agent_hub = Hub(id="hub-ag-1", name="Agent Hub", slug="ag-hub", hub_type="agent", owner_id="user-canvas-1")
        # Ingestion hub (linked target)
        ing_hub = Hub(id="hub-ing-1", name="Ingestion Hub", slug="ing-hub", hub_type="ingestion", owner_id="user-canvas-1")
        # A second agent hub (for the 2-incoming-links test)
        agent_hub_2 = Hub(id="hub-ag-2", name="Agent Hub Two", slug="ag-hub-2", hub_type="agent", owner_id="user-canvas-1")
        # An eval hub with no links (for the empty-incoming test)
        eval_hub = Hub(id="hub-eval-1", name="Eval Hub", slug="eval-hub", hub_type="eval", owner_id="user-canvas-1")

        session.add_all([user, wf_hub, agent_hub, ing_hub, agent_hub_2, eval_hub])

        # Memberships (owner on each hub)
        session.add_all([
            HubMember(hub_id="hub-wf-1", user_id="user-canvas-1", hub_role="owner"),
            HubMember(hub_id="hub-ag-1", user_id="user-canvas-1", hub_role="owner"),
            HubMember(hub_id="hub-ing-1", user_id="user-canvas-1", hub_role="owner"),
            HubMember(hub_id="hub-ag-2", user_id="user-canvas-1", hub_role="owner"),
            HubMember(hub_id="hub-eval-1", user_id="user-canvas-1", hub_role="owner"),
        ])

        # Links: wf -> agent, wf -> ingestion, agent2 -> wf (incoming to wf)
        session.add_all([
            HubLink(id="link-wf-ag", source_hub_id="hub-wf-1", target_hub_id="hub-ag-1", access_level="use"),
            HubLink(id="link-wf-ing", source_hub_id="hub-wf-1", target_hub_id="hub-ing-1", access_level="read"),
            HubLink(id="link-ag2-wf", source_hub_id="hub-ag-2", target_hub_id="hub-wf-1", access_level="use"),
        ])
        await session.commit()

    async def _get_test_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_async_db] = _get_test_db
    yield session_factory, "hub-wf-1"
    app.dependency_overrides.clear()
    await engine.dispose()


async def _create_workflow(ac: AsyncClient, hub_id: str, name: str = "Canvas WF") -> str:
    res = await ac.post(
        f"/api/hubs/{hub_id}/workflows",
        json={"name": name, "slug": name.lower().replace(" ", "-"), "description": "test"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


# --- Draft persistence tests (B1, B2, B3, B7) ---


@pytest.mark.asyncio
async def test_draft_put_returns_workflow_version(test_db):
    """B1: PUT /{wf_id}/draft with a valid graph returns nodes/edges matching input."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        wf_id = await _create_workflow(ac, hub_id)
        graph = {
            "nodes": [
                {"id": "n1", "type": "start", "data": {}, "position": {"x": 60, "y": 120}},
                {"id": "n2", "type": "agent", "data": {}, "position": {"x": 380, "y": 120}},
            ],
            "edges": [{"source": "n1", "sourceHandle": "out", "target": "n2", "targetHandle": "in"}],
        }
        res = await ac.put(f"/api/hubs/{hub_id}/workflows/{wf_id}/draft", json=graph)
        assert res.status_code == 200, res.text
        body = res.json()
        g = body["graph_json"]
        assert g["nodes"][0]["id"] == "n1"
        assert g["nodes"][1]["id"] == "n2"
        assert g["edges"][0]["source"] == "n1"
        assert g["edges"][0]["target"] == "n2"


@pytest.mark.asyncio
async def test_draft_get_returns_saved_graph(test_db):
    """B2: GET /{wf_id}/draft returns the graph saved in B1."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        wf_id = await _create_workflow(ac, hub_id)
        graph = {
            "nodes": [{"id": "n1", "type": "start", "data": {}, "position": {"x": 60, "y": 120}}],
            "edges": [],
        }
        res_put = await ac.put(f"/api/hubs/{hub_id}/workflows/{wf_id}/draft", json=graph)
        assert res_put.status_code == 200, res_put.text

        res_get = await ac.get(f"/api/hubs/{hub_id}/workflows/{wf_id}/draft")
        assert res_get.status_code == 200, res_get.text
        body = res_get.json()
        g = body["graph_json"]
        assert g["nodes"][0]["id"] == "n1"
        assert g["edges"] == []


@pytest.mark.asyncio
async def test_draft_put_with_empty_graph(test_db):
    """B3: PUT /{wf_id}/draft with { nodes: [], edges: [] } returns 200 (not 422)."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        wf_id = await _create_workflow(ac, hub_id)
        res = await ac.put(f"/api/hubs/{hub_id}/workflows/{wf_id}/draft", json={"nodes": [], "edges": []})
        assert res.status_code == 200, res.text
        body = res.json()
        g = body["graph_json"]
        assert g["nodes"] == []
        assert g["edges"] == []


@pytest.mark.asyncio
async def test_metadata_update_does_not_clobber_draft(test_db):
    """B7: PUT /{wf_id} (metadata) does not clobber the saved draft graph."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        wf_id = await _create_workflow(ac, hub_id, name="Original Name")
        graph = {
            "nodes": [{"id": "n1", "type": "start", "data": {}, "position": {"x": 60, "y": 120}}],
            "edges": [],
        }
        res_put = await ac.put(f"/api/hubs/{hub_id}/workflows/{wf_id}/draft", json=graph)
        assert res_put.status_code == 200, res_put.text

        # Update metadata only (PATCH /{wf_id})
        res_meta = await ac.patch(f"/api/hubs/{hub_id}/workflows/{wf_id}", json={"name": "Renamed"})
        assert res_meta.status_code == 200, res_meta.text
        assert res_meta.json()["name"] == "Renamed"

        # Draft graph must be unchanged
        res_get = await ac.get(f"/api/hubs/{hub_id}/workflows/{wf_id}/draft")
        assert res_get.status_code == 200, res_get.text
        assert res_get.json()["graph_json"]["nodes"][0]["id"] == "n1"


# --- Links direction tests (B4, B5, B6) ---


@pytest.mark.asyncio
async def test_links_direction_incoming(test_db):
    """B4: GET /{hub_id}/links?direction=incoming returns links targeting this hub."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/hubs/{hub_id}/links?direction=incoming")
        assert res.status_code == 200, res.text
        links = res.json()
        # hub-wf-1 is the target of exactly one link (agent2 -> wf)
        assert len(links) == 1
        assert links[0]["target_hub_id"] == hub_id
        assert links[0]["source_hub_id"] == "hub-ag-2"


@pytest.mark.asyncio
async def test_links_direction_outgoing_default(test_db):
    """B5: GET /{hub_id}/links (no direction) returns only outgoing links."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/hubs/{hub_id}/links")
        assert res.status_code == 200, res.text
        links = res.json()
        # hub-wf-1 has two outgoing links (wf->agent, wf->ingestion)
        assert len(links) == 2
        for link in links:
            assert link["source_hub_id"] == hub_id
        # None of them should be the incoming link (agent2 -> wf)
        assert all(link["target_hub_id"] != "hub-wf-1" for link in links)


@pytest.mark.asyncio
async def test_links_direction_incoming_empty(test_db):
    """B6: GET /{hub_id}/links?direction=incoming for a hub with no incoming links returns []."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # hub-eval-1 has no links at all
        res = await ac.get("/api/hubs/hub-eval-1/links?direction=incoming")
        assert res.status_code == 200, res.text
        assert res.json() == []


@pytest.mark.asyncio
async def test_links_direction_outgoing_returns_linked_hub_ids(test_db):
    """13_03 B1: outgoing links expose the correct target_hub_id values."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/hubs/{hub_id}/links")
        assert res.status_code == 200, res.text
        links = res.json()
        target_ids = {link["target_hub_id"] for link in links}
        assert target_ids == {"hub-ag-1", "hub-ing-1"}
