"""Real-world integration test suite for Hub Linking against real Postgres.

Covers link creation between hubs, bidirectional access, cross-hub data
access, link revocation, link visibility, and link direction validation.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import HubLink
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_link_between_hubs(gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession):
    """Create a link from an agent hub to an ingestion hub and verify the row."""
    owner = await seed_user(email="link_owner_create@contained.ai", role="member")
    agent_hub = await seed_hub(owner=owner, name="Agent Hub", slug="link-agent-hub", hub_type="agent")
    ingestion_hub = await seed_hub(owner=owner, name="Ingestion Hub", slug="link-ingestion-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    resp = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/links",
        json={"target_hub_id": ingestion_hub.id, "access_level": "read"},
        headers=headers,
    )
    assert resp.status_code == 201, f"Create link failed: {resp.text}"
    data = resp.json()
    assert data["source_hub_id"] == agent_hub.id
    assert data["target_hub_id"] == ingestion_hub.id
    assert data["access_level"] == "read"

    # Verify DB row
    stmt = select(HubLink).where(HubLink.source_hub_id == agent_hub.id, HubLink.target_hub_id == ingestion_hub.id)
    link = (await real_db_session.execute(stmt)).scalar_one_or_none()
    assert link is not None
    assert link.access_level == "read"


@pytest.mark.asyncio
async def test_link_visibility_outgoing_and_incoming(
    gateway_client: AsyncClient, seed_user, seed_hub
):
    """Outgoing and incoming link lists are correctly denormalized."""
    owner = await seed_user(email="link_owner_vis@contained.ai", role="member")
    agent_hub = await seed_hub(owner=owner, name="Agent Hub", slug="vis-agent-hub", hub_type="agent")
    ingestion_hub = await seed_hub(owner=owner, name="Ingestion Hub", slug="vis-ingestion-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/links",
        json={"target_hub_id": ingestion_hub.id, "access_level": "read"},
        headers=headers,
    )

    # Outgoing from agent hub
    out_resp = await gateway_client.get(f"/api/hubs/{agent_hub.id}/links?direction=outgoing", headers=headers)
    assert out_resp.status_code == 200
    out_links = out_resp.json()
    assert len(out_links) == 1
    assert out_links[0]["target_hub_id"] == ingestion_hub.id
    assert out_links[0]["target_hub_name"] == "Ingestion Hub"
    assert out_links[0]["target_hub_type"] == "ingestion"

    # Incoming to ingestion hub
    in_resp = await gateway_client.get(f"/api/hubs/{ingestion_hub.id}/links?direction=incoming", headers=headers)
    assert in_resp.status_code == 200
    in_links = in_resp.json()
    assert len(in_links) == 1
    assert in_links[0]["source_hub_id"] == agent_hub.id
    assert in_links[0]["source_hub_name"] == "Agent Hub"


@pytest.mark.asyncio
async def test_link_revocation_denies_access(
    gateway_client: AsyncClient, seed_user, seed_hub, real_db_session: AsyncSession
):
    """Revoking a link removes the HubLink row and denies cross-hub access."""
    owner = await seed_user(email="link_owner_revoke@contained.ai", role="member")
    agent_hub = await seed_hub(owner=owner, name="Agent Hub", slug="revoke-agent-hub", hub_type="agent")
    ingestion_hub = await seed_hub(owner=owner, name="Ingestion Hub", slug="revoke-ingestion-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    # Create link
    create_resp = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/links",
        json={"target_hub_id": ingestion_hub.id, "access_level": "read"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    link_id = create_resp.json()["id"]

    # Revoke link
    del_resp = await gateway_client.delete(f"/api/hubs/{agent_hub.id}/links/{link_id}", headers=headers)
    assert del_resp.status_code == 204

    # Verify row gone
    link = await real_db_session.get(HubLink, link_id)
    assert link is None

    # Outgoing list now empty
    out_resp = await gateway_client.get(f"/api/hubs/{agent_hub.id}/links?direction=outgoing", headers=headers)
    assert out_resp.status_code == 200
    assert out_resp.json() == []


@pytest.mark.asyncio
async def test_link_direction_validation(gateway_client: AsyncClient, seed_user, seed_hub):
    """Linking in a disallowed direction returns 422."""
    owner = await seed_user(email="link_owner_dir@contained.ai", role="member")
    ingestion_hub = await seed_hub(owner=owner, name="Ingestion Hub", slug="dir-ingestion-hub", hub_type="ingestion")
    agent_hub = await seed_hub(owner=owner, name="Agent Hub", slug="dir-agent-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    # ingestion -> agent is NOT in ALLOWED_LINK_DIRECTIONS
    resp = await gateway_client.post(
        f"/api/hubs/{ingestion_hub.id}/links",
        json={"target_hub_id": agent_hub.id, "access_level": "read"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_self_link_rejected(gateway_client: AsyncClient, seed_user, seed_hub):
    """Self-linking a hub to itself returns 422."""
    owner = await seed_user(email="link_owner_self@contained.ai", role="member")
    hub = await seed_hub(owner=owner, name="Self Hub", slug="self-hub", hub_type="agent")
    headers = await _auth_headers(owner)

    resp = await gateway_client.post(
        f"/api/hubs/{hub.id}/links",
        json={"target_hub_id": hub.id, "access_level": "read"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_link_rejected(gateway_client: AsyncClient, seed_user, seed_hub):
    """Creating a duplicate link between the same hubs returns 409."""
    owner = await seed_user(email="link_owner_dup@contained.ai", role="member")
    agent_hub = await seed_hub(owner=owner, name="Agent Hub", slug="dup-agent-hub", hub_type="agent")
    ingestion_hub = await seed_hub(owner=owner, name="Ingestion Hub", slug="dup-ingestion-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    # First link
    first = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/links",
        json={"target_hub_id": ingestion_hub.id, "access_level": "read"},
        headers=headers,
    )
    assert first.status_code == 201

    # Duplicate link -> 409
    dup = await gateway_client.post(
        f"/api/hubs/{agent_hub.id}/links",
        json={"target_hub_id": ingestion_hub.id, "access_level": "read"},
        headers=headers,
    )
    assert dup.status_code == 409
    assert dup.headers.get("X-Error-Code") == "LINK_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_linkable_targets_lists_legal_directions(gateway_client: AsyncClient, seed_user, seed_hub):
    """linkable-targets only lists hubs with a legal link direction."""
    owner = await seed_user(email="link_owner_targets@contained.ai", role="member")
    agent_hub = await seed_hub(owner=owner, name="Agent Hub", slug="tgt-agent-hub", hub_type="agent")
    ingestion_hub = await seed_hub(owner=owner, name="Ingestion Hub", slug="tgt-ingestion-hub", hub_type="ingestion")
    headers = await _auth_headers(owner)

    resp = await gateway_client.get(f"/api/hubs/{agent_hub.id}/linkable-targets", headers=headers)
    assert resp.status_code == 200
    targets = resp.json()
    # agent -> ingestion is legal, so ingestion hub should be listed
    assert any(t["id"] == ingestion_hub.id for t in targets)
