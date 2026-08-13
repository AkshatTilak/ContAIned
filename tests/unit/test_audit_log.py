
import pytest
pytestmark = pytest.mark.unit
"""Unit tests for audit logging service, redaction, and admin endpoint (S6-02e)."""

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.clients.postgres import get_async_db
from common.models.database import Base, User
from common.services.audit import client_ip, record_audit, redact
from gateway.api.admin_audit import router as admin_audit_router


def test_redaction_helper():
    """Test recursive key redaction and sensitive key dropping."""
    payload = {
        "name": "Datastore",
        "api_key": "sk-secret-12345",
        "credentials_encrypted": "encrypted-blob",
        "password_hash": "hash-val",
        "config": {
            "token": "tok-999",
            "password": "my-password",
            "host": "localhost",
        },
    }
    redacted = redact(payload)
    assert redacted["name"] == "Datastore"
    assert redacted["api_key"] == "***"
    assert "credentials_encrypted" not in redacted
    assert "password_hash" not in redacted
    assert redacted["config"]["token"] == "***"
    assert redacted["config"]["password"] == "***"
    assert redacted["config"]["host"] == "localhost"


@pytest.fixture
def dummy_request():
    class DummyClient:
        host = "192.168.1.50"

    app = FastAPI()
    req = Request({"type": "http", "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18")], "client": ("192.168.1.50", 1234)})
    return req


def test_client_ip_extraction_without_trust_proxy(dummy_request):
    """TRUST_PROXY_HEADERS=False ignores X-Forwarded-For."""
    ip = client_ip(dummy_request)
    assert ip == "192.168.1.50"


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        admin_u = User(id="u-admin", email="admin@example.com", platform_role="admin")
        member_u = User(id="u-member", email="member@example.com", platform_role="member")
        session.add_all([admin_u, member_u])
        await session.commit()

        # Seed audit log
        await record_audit(
            session,
            action="create",
            resource_type="hub",
            hub_id="hub-100",
            actor_user_id="u-admin",
            resource_id="hub-100",
            summary="Created test hub",
        )
        await session.commit()

        yield session

    await engine.dispose()


def build_audit_admin_app(session: AsyncSession):
    app = FastAPI()

    async def _get_db_override():
        yield session

    app.dependency_overrides[get_async_db] = _get_db_override

    @app.middleware("http")
    async def inject_user_middleware(request: Request, call_next):
        hdr = request.headers.get("X-Test-User", "admin")
        if hdr == "member":
            request.state.user = {"sub": "u-member", "email": "member@example.com", "platform_role": "member"}
        else:
            request.state.user = {"sub": "u-admin", "email": "admin@example.com", "platform_role": "admin"}
        return await call_next(request)

    app.include_router(admin_audit_router, prefix="/api")
    return app


@pytest.mark.asyncio
async def test_admin_audit_endpoint_permissions(async_session: AsyncSession):
    """GET /api/admin/audit is 403 for member, 200 for admin, and 422 for limit > 200."""
    app = build_audit_admin_app(async_session)
    client = TestClient(app)

    # Member -> 403
    r_mem = client.get("/api/admin/audit", headers={"X-Test-User": "member"})
    assert r_mem.status_code == 403

    # Admin -> 200
    r_admin = client.get("/api/admin/audit", headers={"X-Test-User": "admin"})
    assert r_admin.status_code == 200
    records = r_admin.json()
    assert len(records) >= 1
    assert records[0]["action"] == "create"

    # Limit > 200 -> 422
    r_limit = client.get("/api/admin/audit?limit=500", headers={"X-Test-User": "admin"})
    assert r_limit.status_code == 422
