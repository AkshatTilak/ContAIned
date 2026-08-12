"""Hub-scoped Gateway REST API for External Database Credentials Vault (Task 12).

Routes under `/hubs/{hub_id}/db-credentials`:
- `GET /hubs/{hub_id}/db-credentials`         - List credentials in hub
- `POST /hubs/{hub_id}/db-credentials`        - Create external DB credential
- `GET /hubs/{hub_id}/db-credentials/{id}`    - Get credential summary (no secrets)
- `PUT /hubs/{hub_id}/db-credentials/{id}`    - Update credential
- `DELETE /hubs/{hub_id}/db-credentials/{id}` - Delete credential
- `POST /hubs/{hub_id}/db-credentials/{id}/test` - Test database connection
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.postgres import get_async_db
from common.models.database import ExternalCredential
from common.security.crypto import encrypt_credential_payload, decrypt_credential_payload
from common.clients.db_connectors.pool_manager import ConnectorPoolManager, get_connector
from gateway.auth.hub_context import HubContext, require_hub
from common.observability.logger import get_logger

logger = get_logger("gateway.api.db_credentials")

router = APIRouter(prefix="/hubs/{hub_id}/db-credentials", tags=["External Database Credentials"])


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class DBCredentialCreatePayload(BaseModel):
    name: str = Field(..., max_length=200, description="Human readable name e.g. Production Analytics")
    db_type: str = Field(..., description="postgres | mysql | mongodb | redis | snowflake | bigquery")
    host: Optional[str] = Field(None, max_length=500)
    port: Optional[int] = None
    database_name: Optional[str] = Field(None, max_length=200)
    username: Optional[str] = Field(None, max_length=200)
    password: Optional[str] = Field(None, description="Raw password, encrypted at rest")
    extra_payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="SSL certs, tokens")
    is_read_only: bool = Field(True, description="Enforce read-only transactions")
    max_connections: int = Field(10, ge=1, le=50)


class DBCredentialUpdatePayload(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    host: Optional[str] = Field(None, max_length=500)
    port: Optional[int] = None
    database_name: Optional[str] = Field(None, max_length=200)
    username: Optional[str] = Field(None, max_length=200)
    password: Optional[str] = Field(None)
    extra_payload: Optional[Dict[str, Any]] = None
    is_read_only: Optional[bool] = None
    max_connections: Optional[int] = Field(None, ge=1, le=50)


class DBCredentialResponse(BaseModel):
    id: str
    hub_id: str
    name: str
    db_type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    is_read_only: bool
    max_connections: int
    has_secret: bool = False
    created_at: datetime
    updated_at: datetime


class DBCredentialTestResult(BaseModel):
    credential_id: str
    success: bool
    message: str
    latency_ms: float = 0.0


def _to_response(cred: ExternalCredential) -> DBCredentialResponse:
    """Build response model guaranteed never to leak secret payloads."""
    return DBCredentialResponse(
        id=str(cred.id),
        hub_id=str(cred.hub_id),
        name=cred.name,
        db_type=cred.db_type,
        host=cred.host,
        port=cred.port,
        database_name=cred.database_name,
        username=cred.username,
        is_read_only=cred.is_read_only,
        max_connections=cred.max_connections,
        has_secret=bool(cred.encrypted_secret_payload),
        created_at=cred.created_at,
        updated_at=cred.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[DBCredentialResponse])
async def list_db_credentials(
    hub_id: str,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(min_role="viewer")),
) -> List[DBCredentialResponse]:
    """List all external database credentials registered in this hub."""
    stmt = (
        select(ExternalCredential)
        .where(ExternalCredential.hub_id == hub_id)
        .order_by(ExternalCredential.name)
    )
    creds = (await db.execute(stmt)).scalars().all()
    return [_to_response(c) for c in creds]


@router.post("", response_model=DBCredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_db_credential(
    hub_id: str,
    payload: DBCredentialCreatePayload,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(min_role="contributor")),
) -> DBCredentialResponse:
    """Create a new encrypted external database credential."""
    # Check duplicate name in hub
    stmt_dup = select(ExternalCredential).where(
        ExternalCredential.hub_id == hub_id,
        ExternalCredential.name == payload.name,
    )
    if (await db.execute(stmt_dup)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Credential with name '{payload.name}' already exists in this hub.",
        )

    secret_data: Dict[str, Any] = payload.extra_payload or {}
    if payload.password:
        secret_data["password"] = payload.password

    encrypted_payload = encrypt_credential_payload(secret_data) if secret_data else None

    cred = ExternalCredential(
        hub_id=hub_id,
        name=payload.name,
        db_type=payload.db_type.lower(),
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        encrypted_secret_payload=encrypted_payload,
        is_read_only=payload.is_read_only,
        max_connections=payload.max_connections,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return _to_response(cred)


@router.get("/{credential_id}", response_model=DBCredentialResponse)
async def get_db_credential(
    hub_id: str,
    credential_id: str,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(min_role="viewer")),
) -> DBCredentialResponse:
    """Get credential metadata (never returning secrets)."""
    stmt = select(ExternalCredential).where(
        ExternalCredential.hub_id == hub_id,
        ExternalCredential.id == credential_id,
    )
    cred = (await db.execute(stmt)).scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="DB credential not found.")
    return _to_response(cred)


@router.put("/{credential_id}", response_model=DBCredentialResponse)
async def update_db_credential(
    hub_id: str,
    credential_id: str,
    payload: DBCredentialUpdatePayload,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(min_role="contributor")),
) -> DBCredentialResponse:
    """Update external database credential parameters."""
    stmt = select(ExternalCredential).where(
        ExternalCredential.hub_id == hub_id,
        ExternalCredential.id == credential_id,
    )
    cred = (await db.execute(stmt)).scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="DB credential not found.")

    if payload.name is not None:
        cred.name = payload.name
    if payload.host is not None:
        cred.host = payload.host
    if payload.port is not None:
        cred.port = payload.port
    if payload.database_name is not None:
        cred.database_name = payload.database_name
    if payload.username is not None:
        cred.username = payload.username
    if payload.is_read_only is not None:
        cred.is_read_only = payload.is_read_only
    if payload.max_connections is not None:
        cred.max_connections = payload.max_connections

    if payload.password is not None or payload.extra_payload is not None:
        # Re-encrypt payload
        existing: Dict[str, Any] = {}
        if cred.encrypted_secret_payload:
            try:
                existing = decrypt_credential_payload(cred.encrypted_secret_payload)
            except Exception:
                pass
        if payload.extra_payload is not None:
            existing.update(payload.extra_payload)
        if payload.password is not None:
            existing["password"] = payload.password
        cred.encrypted_secret_payload = encrypt_credential_payload(existing)

    cred.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(cred)

    # Invalidate pool manager cache
    manager = ConnectorPoolManager.get_instance()
    await manager.remove_connector(credential_id)

    return _to_response(cred)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_db_credential(
    hub_id: str,
    credential_id: str,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(min_role="maintainer")),
) -> None:
    """Delete database credential profile and close its active pool."""
    stmt = select(ExternalCredential).where(
        ExternalCredential.hub_id == hub_id,
        ExternalCredential.id == credential_id,
    )
    cred = (await db.execute(stmt)).scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="DB credential not found.")

    await db.delete(cred)
    await db.commit()

    manager = ConnectorPoolManager.get_instance()
    await manager.remove_connector(credential_id)


@router.post("/{credential_id}/test", response_model=DBCredentialTestResult)
async def test_db_credential(
    hub_id: str,
    credential_id: str,
    db: AsyncSession = Depends(get_async_db),
    ctx: HubContext = Depends(require_hub(min_role="viewer")),
) -> DBCredentialTestResult:
    """Test connectivity to an external database."""
    import time
    stmt = select(ExternalCredential).where(
        ExternalCredential.hub_id == hub_id,
        ExternalCredential.id == credential_id,
    )
    cred = (await db.execute(stmt)).scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="DB credential not found.")

    start = time.monotonic()
    try:
        connector = await get_connector(cred)
        ok = await connector.test_connection()
        latency = round((time.monotonic() - start) * 1000, 2)
        return DBCredentialTestResult(
            credential_id=credential_id,
            success=ok,
            message="Connection successful" if ok else "Connection test ping returned False",
            latency_ms=latency,
        )
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000, 2)
        return DBCredentialTestResult(
            credential_id=credential_id,
            success=False,
            message=f"Connection failed: {exc}",
            latency_ms=latency,
        )
