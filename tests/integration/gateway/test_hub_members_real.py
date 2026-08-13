"""Real-world integration test suite for Hub Membership against real Postgres.

Covers member add/remove, role escalation/demotion, owner transfer, last-owner
protection, and member-vs-admin hub creation permission differences.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import HubMember
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_add_member_with_role(gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession):
    """Add a member with a role and verify the HubMember row is created."""
    owner = await seed_user(email="mem_owner_add@contained.ai", role="member")
    member = await seed_user(email="mem_target_add@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Add Member Hub", slug="add-member-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/members",
        json={"user_id": member.id, "hub_role": "contributor"},
        headers=headers,
    )
    assert resp.status_code == 201, f"Add member failed: {resp.text}"
    data = resp.json()
    assert data["user_id"] == member.id
    assert data["hub_role"] == "contributor"

    # Verify DB row
    stmt = select(HubMember).where(HubMember.hub_id == hub.id, HubMember.user_id == member.id)
    row = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert row is not None
    assert row.hub_role == "contributor"


@pytest.mark.asyncio
async def test_role_escalation_and_demotion(gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession):
    """Escalate member -> admin, then demote admin -> viewer."""
    owner = await seed_user(email="mem_owner_roles@contained.ai", role="member")
    member = await seed_user(email="mem_target_roles@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Role Hub", slug="role-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    # Add as viewer
    add_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/members",
        json={"user_id": member.id, "hub_role": "viewer"},
        headers=headers,
    )
    assert add_resp.status_code == 201

    # Escalate to maintainer
    esc_resp = await gateway_client.patch(
        f"/api/hubs/{hub.id}/members/{member.id}",
        json={"hub_role": "maintainer"},
        headers=headers,
    )
    assert esc_resp.status_code == 200
    assert esc_resp.json()["hub_role"] == "maintainer"

    # Demote to viewer
    dem_resp = await gateway_client.patch(
        f"/api/hubs/{hub.id}/members/{member.id}",
        json={"hub_role": "viewer"},
        headers=headers,
    )
    assert dem_resp.status_code == 200
    assert dem_resp.json()["hub_role"] == "viewer"

    # Verify persisted
    await real_db_session.refresh(hub)
    stmt = select(HubMember).where(HubMember.hub_id == hub.id, HubMember.user_id == member.id)
    row = (await real_db_session.execute(stmt)).scalar_one()
    assert row.hub_role == "viewer"


@pytest.mark.asyncio
async def test_remove_member_revokes_access(gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession):
    """Removing a member revokes their access to the hub."""
    owner = await seed_user(email="mem_owner_remove@contained.ai", role="member")
    member = await seed_user(email="mem_target_remove@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Remove Hub", slug="remove-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    # Add member
    await gateway_client.post(
        f"/api/hubs/{hub.id}/members",
        json={"user_id": member.id, "hub_role": "viewer"},
        headers=headers,
    )

    # Remove member
    del_resp = await gateway_client.delete(f"/api/hubs/{hub.id}/members/{member.id}", headers=headers)
    assert del_resp.status_code == 204

    # Verify row gone
    stmt = select(HubMember).where(HubMember.hub_id == hub.id, HubMember.user_id == member.id)
    row = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert row is None

    # Removed member can no longer access hub (404 anti-enumeration)
    member_headers = await _auth_headers(member)
    access_resp = await gateway_client.get(f"/api/hubs/{hub.id}", headers=member_headers)
    assert access_resp.status_code == 404


@pytest.mark.asyncio
async def test_owner_transfer(gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession):
    """Transfer ownership to another member; previous owner demoted to maintainer."""
    owner = await seed_user(email="mem_owner_transfer@contained.ai", role="member")
    new_owner = await seed_user(email="mem_new_owner@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Transfer Hub", slug="transfer-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    # Add new owner as member first
    await gateway_client.post(
        f"/api/hubs/{hub.id}/members",
        json={"user_id": new_owner.id, "hub_role": "maintainer"},
        headers=headers,
    )

    # Transfer ownership
    transfer_resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/transfer-ownership",
        json={"new_owner_user_id": new_owner.id, "keep_previous_owner": False},
        headers=headers,
    )
    assert transfer_resp.status_code == 200
    assert transfer_resp.json()["owner_id"] == new_owner.id

    # Verify DB: hub owner_id updated
    await real_db_session.refresh(hub)
    assert hub.owner_id == new_owner.id

    # New owner is owner role
    stmt_new = select(HubMember).where(HubMember.hub_id == hub.id, HubMember.user_id == new_owner.id)
    new_row = (await real_db_session.execute(stmt_new)).scalar_one()
    assert new_row.hub_role == "owner"

    # Previous owner demoted to maintainer
    stmt_old = select(HubMember).where(HubMember.hub_id == hub.id, HubMember.user_id == owner.id)
    old_row = (await real_db_session.execute(stmt_old)).scalar_one()
    assert old_row.hub_role == "maintainer"


@pytest.mark.asyncio
async def test_last_owner_cannot_be_demoted_or_removed(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """The last owner of a hub cannot be demoted or removed."""
    owner = await seed_user(email="mem_owner_last@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Last Owner Hub", slug="last-owner-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    # Attempt to demote last owner -> 409
    dem_resp = await gateway_client.patch(
        f"/api/hubs/{hub.id}/members/{owner.id}",
        json={"hub_role": "viewer"},
        headers=headers,
    )
    assert dem_resp.status_code == 409
    assert dem_resp.headers.get("X-Error-Code") == "LAST_OWNER"

    # Attempt to remove last owner -> 409
    del_resp = await gateway_client.delete(f"/api/hubs/{hub.id}/members/{owner.id}", headers=headers)
    assert del_resp.status_code == 409


@pytest.mark.asyncio
async def test_member_can_create_hub_when_allowed(
    gateway_client: AsyncClient, seed_user, monkeypatch
):
    """When ALLOW_MEMBER_HUB_CREATION is true, a member can create a hub."""
    from common.config.settings import settings
    monkeypatch.setattr(settings, "ALLOW_MEMBER_HUB_CREATION", True)

    member = await seed_user(email="mem_creator_allowed@contained.ai", role="member")
    headers = await _auth_headers(member)

    resp = await gateway_client.post(
        "/api/hubs",
        json={"name": "Member Created Hub", "slug": "member-created", "hub_type": "agent"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["owner_id"] == member.id


@pytest.mark.asyncio
async def test_member_cannot_create_hub_when_disallowed(
    gateway_client: AsyncClient, seed_user, monkeypatch
):
    """When ALLOW_MEMBER_HUB_CREATION is false, a member gets 403; admin still can."""
    from common.config.settings import settings
    monkeypatch.setattr(settings, "ALLOW_MEMBER_HUB_CREATION", False)

    member = await seed_user(email="mem_creator_blocked@contained.ai", role="member")
    admin = await seed_user(email="mem_admin_creator@contained.ai", role="admin")

    member_headers = await _auth_headers(member)
    admin_headers = await _auth_headers(admin)

    # Member -> 403
    mem_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": "Blocked Hub", "slug": "blocked-hub", "hub_type": "agent"},
        headers=member_headers,
    )
    assert mem_resp.status_code == 403

    # Admin -> 201
    adm_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": "Admin Hub", "slug": "admin-created", "hub_type": "agent"},
        headers=admin_headers,
    )
    assert adm_resp.status_code == 201
