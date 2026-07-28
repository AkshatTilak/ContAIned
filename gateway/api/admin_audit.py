"""Admin Audit Log REST API routes (hubs.md §3.5, §7)."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from common.clients.postgres import get_async_db
from common.models.database import AuditLog
from common.schemas.hubs import AuditLogRead
from fastapi import APIRouter, Depends, HTTPException, Query, status
from gateway.auth.dependencies import require_role
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/admin/audit", tags=["admin-audit"])
logger = logging.getLogger("gateway.api.admin_audit")


@router.get("", response_model=List[AuditLogRead])
async def list_audit_logs(
    hub_id: Optional[str] = Query(None),
    actor_user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    admin_user: Dict[str, Any] = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch system audit log records (Platform Admin only)."""
    if limit > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Limit cannot exceed 200",
        )

    stmt = select(AuditLog)

    if hub_id is not None:
        stmt = stmt.where(AuditLog.hub_id == hub_id)
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type is not None:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if resource_id is not None:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    if since is not None:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditLog.created_at <= until)

    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
    res = await db.execute(stmt)
    records = res.scalars().all()
    return records
