"""Real-world Proxy Integration Tests (B8-16 / sub_16_06).

Tests proxy endpoints for infrastructure dashboards (Qdrant/Neo4j) with authentication and RBAC.
"""

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
async def test_proxy_qdrant_dashboard_and_telemetry(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Test proxying Qdrant endpoints with admin permissions against live Qdrant."""
    uid = uuid.uuid4().hex[:8]
    admin = await seed_user(email=f"proxy_admin_{uid}@contained.ai", role="admin")
    headers = await _auth_headers(admin)

    # 1. Access Qdrant Collections via Proxy
    col_resp = await gateway_client.get("/collections", headers=headers)
    assert col_resp.status_code in (200, 502)
    if col_resp.status_code == 200:
        data = col_resp.json()
        assert "result" in data or "collections" in str(data)

    # 2. Access Qdrant Proxy route
    qdrant_resp = await gateway_client.get("/qdrant", headers=headers)
    assert qdrant_resp.status_code in (200, 502)
    if qdrant_resp.status_code == 200:
        assert "X-Frame-Options" in qdrant_resp.headers


@pytest.mark.asyncio
async def test_proxy_rbac_enforcement(
    gateway_client: AsyncClient, seed_user, real_db_session: AsyncSession
):
    """Verify non-admin users cannot access admin-restricted proxy routes."""
    uid = uuid.uuid4().hex[:8]
    member = await seed_user(email=f"proxy_member_{uid}@contained.ai", role="member")
    headers = await _auth_headers(member)

    # Accessing /qdrant requires admin
    qdrant_resp = await gateway_client.get("/qdrant", headers=headers)
    assert qdrant_resp.status_code == 403
