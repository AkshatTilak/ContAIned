"""End-to-End Test: Multi-User Collaboration, invitations, RBAC enforcement, and access revocation."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_multi_user_collaboration_journey(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Admin invites/adds member -> member creates resource -> demoted to viewer -> removed."""
    uid = uuid.uuid4().hex[:8]
    admin = await seed_user(email=f"collab_admin_{uid}@contained.ai", role="admin")
    member = await seed_user(email=f"collab_member_{uid}@contained.ai", role="member")

    admin_headers = await _auth_headers(admin)
    member_headers = await _auth_headers(member)

    # 1. Admin creates Hub
    hub_resp = await gateway_client.post(
        "/api/hubs",
        json={
            "name": f"Collab Hub {uid}",
            "slug": f"collab-hub-{uid}",
            "description": "Multi-user collaboration hub",
            "hub_type": "agent",
        },
        headers=admin_headers,
    )
    assert hub_resp.status_code == 201
    hub_id = hub_resp.json()["id"]

    # 2. Admin adds Member with contributor role
    add_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/members",
        json={
            "user_id": member.id,
            "hub_role": "contributor",
        },
        headers=admin_headers,
    )
    assert add_resp.status_code == 201

    # Verify Member listed in hub members
    members_resp = await gateway_client.get(f"/api/hubs/{hub_id}/members", headers=admin_headers)
    assert members_resp.status_code == 200
    member_ids = [m["user_id"] for m in members_resp.json()]
    assert member.id in member_ids

    # 3. Member creates resource in Hub (Contributor can create agents) with distributed model (gemma-3-12b-it)
    agent_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/agents",
        json={
            "name": f"Member Agent {uid}",
            "slug": f"member-agent-{uid}",
            "role": "assistant",
            "system_prompt": "Collaborative agent assistant.",
            "model_id": "gemini/gemma-3-12b-it",
            "temperature": 0.4,
        },
        headers=member_headers,
    )
    assert agent_resp.status_code == 201
    agent_id = agent_resp.json()["id"]

    # Admin verifies visibility of resource
    admin_view_resp = await gateway_client.get(f"/api/hubs/{hub_id}/agents/{agent_id}", headers=admin_headers)
    assert admin_view_resp.status_code == 200

    # 4. Admin demotes Member to Viewer
    demote_resp = await gateway_client.patch(
        f"/api/hubs/{hub_id}/members/{member.id}",
        json={"hub_role": "viewer"},
        headers=admin_headers,
    )
    assert demote_resp.status_code == 200

    # Member attempts to create another agent (Viewer cannot create) with distributed model (gemma-3-4b-it)
    denied_create_resp = await gateway_client.post(
        f"/api/hubs/{hub_id}/agents",
        json={
            "name": f"Denied Agent {uid}",
            "slug": f"denied-agent-{uid}",
            "role": "assistant",
            "system_prompt": "This should be denied.",
            "model_id": "gemini/gemma-3-4b-it",
        },
        headers=member_headers,
    )
    assert denied_create_resp.status_code in (403, 401)

    # 5. Admin removes Member from Hub
    remove_resp = await gateway_client.delete(
        f"/api/hubs/{hub_id}/members/{member.id}",
        headers=admin_headers,
    )
    assert remove_resp.status_code in (200, 204)

    # Member attempts to access Hub and is denied
    revoked_access_resp = await gateway_client.get(
        f"/api/hubs/{hub_id}",
        headers=member_headers,
    )
    assert revoked_access_resp.status_code in (403, 404)
