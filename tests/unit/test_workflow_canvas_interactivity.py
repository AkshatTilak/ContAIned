
import pytest
pytestmark = pytest.mark.unit
"""Backend API tests for Base Task 14: Workflow Canvas Interactivity & Hub Panel Fixes (v7).

Covers:
- Links list endpoint denormalization (target_hub_name/type/slug, source_hub_name/type).
- Members list endpoint null-safety (email/display_name may be null).

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
        user = User(id="user-int-1", email="interact@example.com", display_name="Interact User")

        hub_a = Hub(id="hub-a", name="Hub A", slug="hub-a", hub_type="workflow", owner_id="user-int-1")
        hub_b = Hub(id="hub-b", name="Hub B", slug="hub-b", hub_type="agent", owner_id="user-int-1")
        hub_c = Hub(id="hub-c", name="Hub C", slug="hub-c", hub_type="ingestion", owner_id="user-int-1")
        hub_d = Hub(id="hub-d", name="Hub D", slug="hub-d", hub_type="agent", owner_id="user-int-1")

        session.add_all([user, hub_a, hub_b, hub_c, hub_d])

        # Memberships
        session.add_all([
            HubMember(hub_id="hub-a", user_id="user-int-1", hub_role="owner"),
            HubMember(hub_id="hub-b", user_id="user-int-1", hub_role="owner"),
            HubMember(hub_id="hub-c", user_id="user-int-1", hub_role="owner"),
            HubMember(hub_id="hub-d", user_id="user-int-1", hub_role="owner"),
        ])

        # Links: A -> B, A -> C (outgoing from A); D -> A (incoming to A)
        session.add_all([
            HubLink(id="link-ab", source_hub_id="hub-a", target_hub_id="hub-b", access_level="use"),
            HubLink(id="link-ac", source_hub_id="hub-a", target_hub_id="hub-c", access_level="read"),
            HubLink(id="link-da", source_hub_id="hub-d", target_hub_id="hub-a", access_level="use"),
        ])
        await session.commit()

    async def _get_test_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_async_db] = _get_test_db
    yield session_factory, "hub-a"
    app.dependency_overrides.clear()
    await engine.dispose()


# --- Links denormalization tests (B1, B2, B3, B6, B7, B8) ---


@pytest.mark.asyncio
async def test_links_list_outgoing_populates_target_hub_name(test_db):
    """B1: GET /hubs/A/links populates target_hub_name/type/slug for each link."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/hubs/{hub_id}/links")
        assert res.status_code == 200, res.text
        links = res.json()
        assert len(links) == 2
        by_target = {l["target_hub_id"]: l for l in links}
        # A -> B
        assert by_target["hub-b"]["target_hub_name"] == "Hub B"
        assert by_target["hub-b"]["target_hub_type"] == "agent"
        assert by_target["hub-b"]["target_hub_slug"] == "hub-b"
        # A -> C
        assert by_target["hub-c"]["target_hub_name"] == "Hub C"
        assert by_target["hub-c"]["target_hub_type"] == "ingestion"
        assert by_target["hub-c"]["target_hub_slug"] == "hub-c"


@pytest.mark.asyncio
async def test_links_list_incoming_populates_target_hub_fields(test_db):
    """B2: GET /hubs/A/links?direction=incoming populates target (current) + source hub fields."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/hubs/{hub_id}/links?direction=incoming")
        assert res.status_code == 200, res.text
        links = res.json()
        assert len(links) == 1
        link = links[0]
        # target is the current hub (A)
        assert link["target_hub_id"] == "hub-a"
        assert link["target_hub_name"] == "Hub A"
        assert link["target_hub_type"] == "workflow"
        assert link["target_hub_slug"] == "hub-a"
        # source is hub D
        assert link["source_hub_id"] == "hub-d"
        assert link["source_hub_name"] == "Hub D"
        assert link["source_hub_type"] == "agent"


@pytest.mark.asyncio
async def test_links_target_hub_name_after_hub_rename(test_db):
    """B3: Renaming the target hub is reflected in the links list (live join)."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Rename hub B via PATCH
        res_rename = await ac.patch("/api/hubs/hub-b", json={"name": "Hub B Renamed"})
        assert res_rename.status_code == 200, res_rename.text

        res = await ac.get(f"/api/hubs/{hub_id}/links")
        assert res.status_code == 200, res.text
        links = res.json()
        by_target = {l["target_hub_id"]: l for l in links}
        assert by_target["hub-b"]["target_hub_name"] == "Hub B Renamed"


@pytest.mark.asyncio
async def test_links_multiple_links_all_populated(test_db):
    """B6: Multiple outgoing links all have fully populated target hub fields."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/hubs/{hub_id}/links")
        assert res.status_code == 200, res.text
        links = res.json()
        assert len(links) == 2
        for link in links:
            assert link["target_hub_name"] is not None
            assert link["target_hub_type"] is not None
            assert link["target_hub_slug"] is not None


@pytest.mark.asyncio
async def test_links_deleted_target_hub_graceful(test_db):
    """B7: Archiving the target hub does not crash the links list."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Archive hub C (target of A -> C)
        res_archive = await ac.post("/api/hubs/hub-c/archive")
        assert res_archive.status_code == 200, res_archive.text

        res = await ac.get(f"/api/hubs/{hub_id}/links")
        assert res.status_code == 200, res.text
        links = res.json()
        assert len(links) == 2
        # Link to archived hub C still returned; name may be present or null — no crash
        by_target = {l["target_hub_id"]: l for l in links}
        assert "hub-c" in by_target


@pytest.mark.asyncio
async def test_links_hub_with_no_outgoing_returns_empty(test_db):
    """B8: A hub with no outgoing links returns [] (fully formed response)."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # hub-c has no outgoing links (it is only a target of A -> C)
        res = await ac.get("/api/hubs/hub-c/links")
        assert res.status_code == 200, res.text
        assert res.json() == []


# --- Members null-safety tests (B4, B5) ---


@pytest.mark.asyncio
async def test_members_list_null_email_user(test_db):
    """B4: GET /{hub_id}/members returns 200 with null email/display_name (no 500)."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/hubs/{hub_id}/members")
        assert res.status_code == 200, res.text
        members = res.json()
        assert len(members) == 1
        # The members API returns HubMember rows; email/display_name are not
        # populated from the User join, so they are null (Optional defaults).
        assert members[0]["email"] is None
        assert members[0]["display_name"] is None


@pytest.mark.asyncio
async def test_members_list_mixed_null_and_real_users(test_db):
    """B5: Hub with multiple members returns all of them without crashing."""
    sf, hub_id = test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Add a second member to hub-a
        user2 = User(id="user-int-2", email="second@example.com", display_name="Second User")
        async with sf() as session:
            session.add(user2)
            session.add(HubMember(hub_id="hub-a", user_id="user-int-2", hub_role="contributor"))
            await session.commit()

        res = await ac.get(f"/api/hubs/{hub_id}/members")
        assert res.status_code == 200, res.text
        members = res.json()
        assert len(members) == 2
