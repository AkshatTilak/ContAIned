"""Authentication and User Management REST API routes."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from common.clients.postgres import get_async_db
from common.config.settings import get_settings
from common.constants.roles import (
    PLATFORM_ROLES,
    PLATFORM_ROLE_ADMIN,
    PLATFORM_ROLE_MEMBER,
)
from common.models.database import User, UserSession
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from gateway.auth.dependencies import get_current_user, require_role
from gateway.auth.providers import oauth
from gateway.auth.utils import create_access_token, hash_token
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("gateway.auth.routes")


class UserRoleUpdate(BaseModel):
    platform_role: str

    @field_validator("platform_role")
    @classmethod
    def validate_platform_role(cls, v: str) -> str:
        if v not in PLATFORM_ROLES:
            raise ValueError(f"Platform role must be one of: {', '.join(PLATFORM_ROLES)}")
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    provider: str
    platform_role: str = PLATFORM_ROLE_MEMBER
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


@router.get("/login/{provider}")
async def oauth_login(provider: str, request: Request):
    """Initiate OAuth2 login flow for specified provider (google/github)."""
    client = getattr(oauth, provider, None)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider '{provider}' is not configured.",
        )

    redirect_uri = request.url_for("oauth_callback", provider=provider)
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}", name="oauth_callback")
async def oauth_callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """Callback handler for OAuth2 logins."""
    client = getattr(oauth, provider, None)
    if not client:
        return RedirectResponse(url="/login?error=provider_not_configured")

    try:
        token = await client.authorize_access_token(request)
    except Exception as e:
        logger.error(f"OAuth token exchange error for {provider}: {e}")
        return RedirectResponse(url=f"/login?error=auth_failed&detail={str(e)}")

    user_info: Dict[str, Any] = {}
    if provider == "google":
        user_info = token.get("userinfo") or {}
        email = user_info.get("email")
        provider_id = user_info.get("sub")
        display_name = user_info.get("name")
        avatar_url = user_info.get("picture")
    elif provider == "github":
        resp = await client.get("user", token=token)
        gh_data = resp.json()
        provider_id = str(gh_data.get("id"))
        display_name = gh_data.get("name") or gh_data.get("login")
        avatar_url = gh_data.get("avatar_url")
        email = gh_data.get("email")

        if not email:
            emails_resp = await client.get("user/emails", token=token)
            emails_data = emails_resp.json()
            for em in emails_data:
                if em.get("primary") and em.get("verified"):
                    email = em.get("email")
                    break

    if not email:
        return RedirectResponse(url="/login?error=missing_email")

    # Query existing user by email
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing_user:
        if not existing_user.is_active:
            return RedirectResponse(url="/login?error=account_deactivated")

        existing_user.last_login = now
        existing_user.avatar_url = avatar_url or existing_user.avatar_url
        existing_user.display_name = display_name or existing_user.display_name
        user = existing_user
    else:
        # Check if this is the first user in system
        count_stmt = select(func.count(User.id))
        count_res = await db.execute(count_stmt)
        user_count = count_res.scalar() or 0

        initial_role = PLATFORM_ROLE_ADMIN if user_count == 0 else PLATFORM_ROLE_MEMBER

        user = User(
            id=str(uuid.uuid4()),
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            provider=provider,
            provider_id=provider_id,
            platform_role=initial_role,
            role=initial_role,
            is_active=True,
            created_at=now,
            last_login=now,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    # Generate JWT
    jwt_token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    token_h = hash_token(jwt_token)
    expires_at = now + timedelta(hours=24)

    # Save session
    session_record = UserSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=token_h,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(session_record)
    await db.commit()

    # Redirect to frontend callback route with JWT
    frontend_url = f"http://localhost:5173/auth/callback?token={jwt_token}"
    response = RedirectResponse(url=frontend_url)
    response.set_cookie("auth_token", jwt_token, httponly=True, max_age=86400)
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch current user identity and permissions."""
    user_id = current_user.get("sub") or current_user.get("id")

    if user_id == "local-admin-id":
        return UserResponse(
            id="local-admin-id",
            email="admin@contained.local",
            display_name="Local Admin",
            avatar_url=None,
            provider="local",
            platform_role=PLATFORM_ROLE_ADMIN,
            is_active=True,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow(),
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Invalidate active session."""
    token = getattr(request.state, "token", None)
    if token:
        token_h = hash_token(token)
        stmt = select(UserSession).where(UserSession.token_hash == token_h)
        res = await db.execute(stmt)
        sess = res.scalar_one_or_none()
        if sess:
            await db.delete(sess)
            await db.commit()

    response.delete_cookie("auth_token")
    return {"status": "logged_out"}


# --- Admin User Management Endpoints ---


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_async_db),
    admin: Dict[str, Any] = Depends(require_role("admin")),
):
    """List all registered users (Admin only)."""
    stmt = select(User).order_by(User.created_at.desc())
    result = await db.execute(stmt)
    users = result.scalars().all()
    return users


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    db: AsyncSession = Depends(get_async_db),
    admin: Dict[str, Any] = Depends(require_role("admin")),
):
    """Update platform role for a specified user (Admin only)."""
    if payload.platform_role not in PLATFORM_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Platform role must be one of: {', '.join(PLATFORM_ROLES)}",
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.platform_role == PLATFORM_ROLE_ADMIN and payload.platform_role != PLATFORM_ROLE_ADMIN:
        admin_count_stmt = select(func.count(User.id)).where(
            User.platform_role == PLATFORM_ROLE_ADMIN, User.is_active.is_(True)
        )
        admin_count = (await db.execute(admin_count_stmt)).scalar() or 0
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot demote the last platform admin",
                headers={"X-Error-Code": "LAST_PLATFORM_ADMIN"},
            )

    user.platform_role = payload.platform_role
    user.role = payload.platform_role
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_async_db),
    admin: Dict[str, Any] = Depends(require_role("admin")),
):
    """Deactivate a user account (Admin only)."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user.is_active = False
    await db.commit()
    return {"status": "deactivated", "id": user_id}
