"""API Key Management CRUD & Stats Endpoints.

Provides endpoints under `/api/settings/api-keys` for creating, listing, updating,
revoking API keys, and querying key usage analytics.
"""

import hashlib
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from common.models.database import APIKeyModel, APIKeyUsageModel
from gateway.auth.dependencies import get_db, get_current_user

router = APIRouter(prefix="/settings/api-keys", tags=["API Keys Management"])


def hash_api_key(raw_key: str) -> str:
    """Hashes a raw API key using SHA-256."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name or description for the key")
    rate_limit: Optional[int] = Field(default=60, ge=1, le=1000, description="Requests per minute limit")


class UpdateAPIKeyRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    rate_limit: Optional[int] = Field(default=None, ge=1, le=1000)
    is_active: Optional[bool] = Field(default=None)


class APIKeyResponse(BaseModel):
    id: int
    prefix: Optional[str]
    name: Optional[str]
    rate_limit: int
    usage_count: int
    is_active: bool
    last_used_at: Optional[datetime] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    raw_key: Optional[str] = None  # Populated only on initial creation


@router.post("", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: CreateAPIKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Generate a new OpenAI-compatible API key.
    
    The raw API key is returned ONLY once in raw_key.
    """
    raw_key = f"sk-{secrets.token_urlsafe(36)}"
    hashed_key = hash_api_key(raw_key)
    prefix = raw_key[:8]

    user_id = current_user.get("id") if current_user else None
    now = datetime.utcnow()

    api_key_obj = APIKeyModel(
        key=hashed_key,
        name=payload.name,
        prefix=prefix,
        rate_limit=payload.rate_limit or 60,
        user_id=user_id,
        is_active=True,
        usage_count=0,
        created_at=now,
    )
    db.add(api_key_obj)
    await db.commit()
    await db.refresh(api_key_obj)

    return APIKeyResponse(
        id=api_key_obj.id,
        prefix=api_key_obj.prefix,
        name=api_key_obj.name,
        rate_limit=api_key_obj.rate_limit,
        usage_count=api_key_obj.usage_count,
        is_active=api_key_obj.is_active,
        last_used_at=api_key_obj.last_used_at,
        created_at=api_key_obj.created_at or now,
        raw_key=raw_key,
    )


@router.get("", response_model=List[APIKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """List all API keys for current user (or all keys if user is unauthenticated or admin)."""
    user_id = current_user.get("id") if current_user else None
    stmt = select(APIKeyModel)
    if user_id and current_user.get("role") != "admin":
        stmt = stmt.where(APIKeyModel.user_id == user_id)
    
    stmt = stmt.order_by(APIKeyModel.created_at.desc())
    result = await db.execute(stmt)
    keys = result.scalars().all()

    return [
        APIKeyResponse(
            id=k.id,
            prefix=k.prefix,
            name=k.name,
            rate_limit=k.rate_limit,
            usage_count=k.usage_count,
            is_active=k.is_active,
            last_used_at=k.last_used_at,
            created_at=k.created_at or datetime.utcnow(),
        )
        for k in keys
    ]


@router.put("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: int,
    payload: UpdateAPIKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Update API key details (name, rate limit, active toggle)."""
    stmt = select(APIKeyModel).where(APIKeyModel.id == key_id)
    res = await db.execute(stmt)
    key_obj = res.scalar_one_or_none()
    if not key_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    if payload.name is not None:
        key_obj.name = payload.name
    if payload.rate_limit is not None:
        key_obj.rate_limit = payload.rate_limit
    if payload.is_active is not None:
        key_obj.is_active = payload.is_active

    await db.commit()
    await db.refresh(key_obj)

    return APIKeyResponse(
        id=key_obj.id,
        prefix=key_obj.prefix,
        name=key_obj.name,
        rate_limit=key_obj.rate_limit,
        usage_count=key_obj.usage_count,
        is_active=key_obj.is_active,
        last_used_at=key_obj.last_used_at,
        created_at=key_obj.created_at or datetime.utcnow(),
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Revoke (delete) an API key."""
    stmt = select(APIKeyModel).where(APIKeyModel.id == key_id)
    res = await db.execute(stmt)
    key_obj = res.scalar_one_or_none()
    if not key_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    await db.delete(key_obj)
    await db.commit()
    return None


@router.get("/{key_id}/usage")
async def get_api_key_usage(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """Get aggregate usage stats and recent usage logs for an API key."""
    stmt = select(APIKeyModel).where(APIKeyModel.id == key_id)
    res = await db.execute(stmt)
    key_obj = res.scalar_one_or_none()
    if not key_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    req_count_stmt = select(func.count(APIKeyUsageModel.id)).where(APIKeyUsageModel.api_key_id == key_id)
    total_requests = (await db.execute(req_count_stmt)).scalar() or 0

    input_tokens_stmt = select(func.sum(APIKeyUsageModel.input_tokens)).where(APIKeyUsageModel.api_key_id == key_id)
    total_input_tokens = (await db.execute(input_tokens_stmt)).scalar() or 0

    output_tokens_stmt = select(func.sum(APIKeyUsageModel.output_tokens)).where(APIKeyUsageModel.api_key_id == key_id)
    total_output_tokens = (await db.execute(output_tokens_stmt)).scalar() or 0

    logs_stmt = (
        select(APIKeyUsageModel)
        .where(APIKeyUsageModel.api_key_id == key_id)
        .order_by(APIKeyUsageModel.created_at.desc())
        .limit(50)
    )
    logs_res = await db.execute(logs_stmt)
    recent_logs = logs_res.scalars().all()

    return {
        "key_id": key_id,
        "prefix": key_obj.prefix,
        "name": key_obj.name,
        "total_requests": total_requests,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "recent_logs": [
            {
                "id": log.id,
                "endpoint": log.endpoint,
                "model_used": log.model_used,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "latency_ms": log.latency_ms,
                "status_code": log.status_code,
                "created_at": log.created_at,
            }
            for log in recent_logs
        ],
    }
