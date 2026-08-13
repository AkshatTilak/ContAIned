"""Real-world integration test suite for Hub Lifecycle against real Postgres.

Covers hub CRUD (create/read/update), archive/restore gating, cascading
cleanup on delete, and slug uniqueness enforcement — all against the real
database via the Gateway ASGI app.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import Hub, HubMember, DatastoreBinding
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    """Build Authorization header for a seeded user."""
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_hub_all_types_and_auto_owner_membership(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Create hubs of each type and verify DB row + auto-membership as owner."""
    owner = await seed_user(email="hub_owner_types@contained.ai", role="member")
    headers = await _auth_headers(owner)

    for hub_type in ("agent", "workflow", "ingestion", "eval"):
        slug = f"type-{hub_type}-{owner.id[:6]}"
        resp = await gateway_client.post(
            "/api/hubs",
            json={"name": f"Type {hub_type} Hub", "slug": slug, "hub_type": hub_type},
            headers=headers,
        )
        assert resp.status_code == 201, f"Create {hub_type} hub failed: {resp.text}"
        data = resp.json()
        assert data["hub_type"] == hub_type
        assert data["slug"] == slug
        assert data["owner_id"] == owner.id

        # Verify DB row exists
        hub = await real_db_session.get(Hub, data["id"])
        assert hub is not None
        assert hub.hub_type == hub_type

        # Verify auto-membership as owner
        stmt = select(HubMember).where(HubMember.hub_id == hub.id, HubMember.user_id == owner.id)
        member = (await real_db_session.execute(stmt)).scalar_one_or_none()
        assert member is not None
        assert member.hub_role == "owner"


@pytest.mark.asyncio
async def test_update_hub_metadata(gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession):
    """Update hub name, slug, description, accent, icon, and settings."""
    owner = await seed_user(email="hub_updater@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Original Name", slug="original-slug", hub_type="agent")
    headers = await _auth_headers(owner)

    resp = await gateway_client.patch(
        f"/api/hubs/{hub.id}",
        json={
            "name": "Updated Name",
            "slug": "updated-slug",
            "description": "A fresh description",
            "accent": "violet",
            "icon": "sparkles",
            "settings_json": {"theme": "dark"},
        },
        headers=headers,
    )
    assert resp.status_code == 200, f"Update hub failed: {resp.text}"
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert data["slug"] == "updated-slug"
    assert data["description"] == "A fresh description"
    assert data["accent"] == "violet"
    assert data["icon"] == "sparkles"
    assert data["settings_json"] == {"theme": "dark"}

    # Verify persisted in DB
    await real_db_session.refresh(hub)
    assert hub.name == "Updated Name"
    assert hub.slug == "updated-slug"


@pytest.mark.asyncio
async def test_archive_restore_gates_access(gateway_client: AsyncClient, seed_user, seed_hub):
    """Archiving a hub gates mutating access; unarchive restores it."""
    owner = await seed_user(email="hub_archiver@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Archive Me", slug="archive-me", hub_type="agent")
    headers = await _auth_headers(owner)

    # Archive
    arch_resp = await gateway_client.post(f"/api/hubs/{hub.id}/archive", headers=headers)
    assert arch_resp.status_code == 200
    assert arch_resp.json()["is_archived"] is True

    # Mutating access on archived hub -> 409
    patch_resp = await gateway_client.patch(
        f"/api/hubs/{hub.id}",
        json={"name": "Should Fail"},
        headers=headers,
    )
    assert patch_resp.status_code == 409

    # Read access still works
    get_resp = await gateway_client.get(f"/api/hubs/{hub.id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["hub"]["is_archived"] is True

    # Unarchive
    unarch_resp = await gateway_client.post(f"/api/hubs/{hub.id}/unarchive", headers=headers)
    assert unarch_resp.status_code == 200
    assert unarch_resp.json()["is_archived"] is False

    # Mutating access restored
    patch2_resp = await gateway_client.patch(
        f"/api/hubs/{hub.id}",
        json={"name": "Restored Name"},
        headers=headers,
    )
    assert patch2_resp.status_code == 200
    assert patch2_resp.json()["name"] == "Restored Name"


@pytest.mark.asyncio
async def test_delete_hub_soft_deletes_and_hides(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Deleting a hub soft-deletes it and removes it from all queries/access."""
    owner = await seed_user(email="hub_deleter@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Delete Me", slug="delete-me", hub_type="ingestion")
    headers = await _auth_headers(owner)

    # Add a datastore binding to verify it is hidden with the hub
    binding = DatastoreBinding(
        hub_id=hub.id,
        name="qdrant-main",
        store_type="qdrant",
        connection_uri="http://localhost:6334",
        is_default=True,
    )
    real_db_session.add(binding)
    await real_db_session.flush()

    # Delete hub (force=True default)
    del_resp = await gateway_client.delete(f"/api/hubs/{hub.id}", headers=headers)
    assert del_resp.status_code == 204

    # Hub soft-deleted
    await real_db_session.refresh(hub)
    assert hub.is_deleted is True
    assert hub.deleted_at is not None

    # Hub no longer accessible via API (404 anti-enumeration)
    get_resp = await gateway_client.get(f"/api/hubs/{hub.id}", headers=headers)
    assert get_resp.status_code == 404

    # Hub no longer appears in list
    list_resp = await gateway_client.get("/api/hubs", headers=headers)
    assert list_resp.status_code == 200
    assert all(h["id"] != hub.id for h in list_resp.json())

    # Datastore binding is hidden with the hub (not returned by list)
    ds_resp = await gateway_client.get(f"/api/hubs/{hub.id}/ingestion/datastores", headers=headers)
    assert ds_resp.status_code == 404


@pytest.mark.asyncio
async def test_hub_slug_uniqueness_enforced(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Creating a hub with a duplicate (hub_type, slug) returns 409."""
    owner = await seed_user(email="hub_slug_dup@contained.ai", role="member")
    await seed_hub(owner=owner, name="First Hub", slug="dup-slug", hub_type="agent")
    headers = await _auth_headers(owner)

    # Same slug, same type -> 409
    dup_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": "Second Hub", "slug": "dup-slug", "hub_type": "agent"},
        headers=headers,
    )
    assert dup_resp.status_code == 409
    assert dup_resp.headers.get("X-Error-Code") == "HUB_SLUG_TAKEN"

    # Same slug, different type -> allowed
    ok_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": "Workflow Hub", "slug": "dup-slug", "hub_type": "workflow"},
        headers=headers,
    )
    assert ok_resp.status_code == 201

    # slug-available endpoint reflects state
    avail_resp = await gateway_client.get(
        "/api/hubs/slug-available",
        params={"hub_type": "agent", "slug": "dup-slug"},
        headers=headers,
    )
    assert avail_resp.status_code == 200
    assert avail_resp.json()["available"] is False


@pytest.mark.asyncio
async def test_list_hubs_returns_only_accessible(gateway_client: AsyncClient, seed_user, seed_hub):
    """A member only sees hubs they belong to; admin sees all."""
    member = await seed_user(email="hub_lister_member@contained.ai", role="member")
    admin = await seed_user(email="hub_lister_admin@contained.ai", role="admin")

    # Member owns one hub
    member_hub = await seed_hub(owner=member, name="Member Hub", slug="member-hub", hub_type="agent")
    # Admin owns another hub the member is NOT part of
    await seed_hub(owner=admin, name="Admin Hub", slug="admin-hub", hub_type="agent")

    member_headers = await _auth_headers(member)
    admin_headers = await _auth_headers(admin)

    # Member sees only their hub
    mem_resp = await gateway_client.get("/api/hubs", headers=member_headers)
    assert mem_resp.status_code == 200
    mem_hubs = mem_resp.json()
    assert len(mem_hubs) == 1
    assert mem_hubs[0]["id"] == member_hub.id
    assert mem_hubs[0]["my_role"] == "owner"

    # Admin sees all hubs
    adm_resp = await gateway_client.get("/api/hubs", headers=admin_headers)
    assert adm_resp.status_code == 200
    adm_hubs = adm_resp.json()
    assert len(adm_hubs) == 2
