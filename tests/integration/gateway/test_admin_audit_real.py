"""Real-world Admin Audit Log Integration Tests (B8-16 / sub_16_05).

Tests audit log entry auto-generation, filtering by hub/actor/action, and RBAC enforcement.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.database import AuditLog
from gateway.auth.utils import create_access_token

pytestmark = pytest.mark.integration


async def _auth_headers(user) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_audit_lifecycle_and_filtering(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Test audit log generation on hub operations, query filtering, and retrieval."""
    uid = uuid.uuid4().hex[:8]
    admin = await seed_user(email=f"audit_admin_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    # 1. Perform Hub operations that generate audit log entries
    hub_resp = await gateway_client.post(
        "/api/hubs",
        json={"name": f"Audit Tracked Hub {uid}", "slug": f"audit-hub-{uid}", "hub_type": "agent"},
        headers=headers,
    )
    assert hub_resp.status_code == 201
    hub_id = hub_resp.json()["id"]

    # 2. Query Audit Log as Admin
    audit_resp = await gateway_client.get("/api/admin/audit", headers=headers)
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert isinstance(logs, list)

    # 3. Query Audit Log filtered by hub_id
    filtered_resp = await gateway_client.get(f"/api/admin/audit?hub_id={hub_id}", headers=headers)
    assert filtered_resp.status_code == 200
    hub_logs = filtered_resp.json()
    assert len(hub_logs) >= 1
    assert all(l["hub_id"] == hub_id for l in hub_logs)

    # 4. Query Audit Log filtered by actor_user_id
    actor_resp = await gateway_client.get(f"/api/admin/audit?actor_user_id={admin.id}", headers=headers)
    assert actor_resp.status_code == 200
    actor_logs = actor_resp.json()
    assert len(actor_logs) >= 1
    assert any(l["hub_id"] == hub_id for l in actor_logs)


@pytest.mark.asyncio
async def test_admin_audit_rbac_enforcement(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Verify non-admin users cannot query audit logs."""
    uid = uuid.uuid4().hex[:8]
    member = await seed_user(email=f"audit_member_{uid}@contained.ai", role="member")
    headers = await _auth_headers(member)

    resp = await gateway_client.get("/api/admin/audit", headers=headers)
    assert resp.status_code == 403
