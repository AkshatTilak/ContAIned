import hashlib
import logging
import secrets
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
from common.models.database import User, UserSession, UserIdentity, PasswordResetToken, AuditLog
from common.observability.exceptions import AccountLockedError, PasswordPolicyError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from gateway.auth.dependencies import get_current_user, require_role
from gateway.auth.passwords import (
    hash_password,
    verify_password,
    needs_rehash,
    validate_password_policy,
)
from gateway.auth.providers import oauth
from gateway.auth.signup_service import resolve_signup
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
    platform_role: str = PLATFORM_ROLE_MEMBER
    status: str = "active"
    created_at: datetime
    last_login: Optional[datetime] = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse



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
        if existing_user.status != "active":
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
            platform_role=initial_role,
            status="active",
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
            platform_role=PLATFORM_ROLE_ADMIN,
            status="active",
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
            User.platform_role == PLATFORM_ROLE_ADMIN, User.status == "active"
        )
        admin_count = (await db.execute(admin_count_stmt)).scalar() or 0
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot demote the last platform admin",
                headers={"X-Error-Code": "LAST_PLATFORM_ADMIN"},
            )

    user.platform_role = payload.platform_role
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

    user.status = "suspended"
    await db.commit()
    return {"status": "deactivated", "id": user_id}


# --- Local Password Authentication Endpoints ---


@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
async def register_user(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Register a new user account with email and password."""
    settings = get_settings()
    allow_self_reg = getattr(settings, "ALLOW_SELF_REGISTRATION", True)
    if not allow_self_reg:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": "SELF_REGISTRATION_DISABLED", "message": "Self registration is currently disabled."},
        )

    norm_email = payload.email.strip().lower()
    validate_password_policy(payload.password, norm_email)

    stmt = select(User).where(User.email == norm_email)
    res = await db.execute(stmt)
    existing_user = res.scalar_one_or_none()

    if existing_user:
        # Non-enumerating response
        return {"status": "registration_received"}

    initial_status, initial_role, invite = await resolve_signup(db, norm_email)

    now = datetime.now(timezone.utc)
    user_id = str(uuid.uuid4())

    user = User(
        id=user_id,
        email=norm_email,
        display_name=payload.display_name,
        platform_role=initial_role,
        status=initial_status,
        password_hash=hash_password(payload.password),
        password_updated_at=now,
        created_at=now,
        last_login=now if initial_status == "active" else None,
    )
    db.add(user)
    await db.flush()

    identity = UserIdentity(
        id=str(uuid.uuid4()),
        user_id=user.id,
        provider="password",
        provider_id=user.id,
        email=norm_email,
        created_at=now,
    )
    db.add(identity)

    if invite:
        invite.status = "accepted"
        invite.accepted_at = now
        invite.accepted_user_id = user.id

    await db.commit()

    return {"status": "registration_received"}


@router.post("/login", response_model=TokenResponse)
async def login_user(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Authenticate user with email and password."""
    norm_email = payload.email.strip().lower()

    stmt = select(User).where(User.email == norm_email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    password_valid = verify_password(payload.password, user.password_hash if user else None)
    now = datetime.now(timezone.utc)

    if user and user.locked_until:
        locked_until_utc = user.locked_until.replace(tzinfo=timezone.utc) if user.locked_until.tzinfo is None else user.locked_until
        if locked_until_utc > now:
            retry_after = max(1, int((locked_until_utc - now).total_seconds()))
            raise AccountLockedError(
                message="Account is temporarily locked due to failed login attempts",
                details={"reason": "ACCOUNT_LOCKED", "retry_after": retry_after},
            )
        else:
            user.locked_until = None
            user.failed_login_count = 0

    if not user or not password_valid:
        if user:
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= 5:
                user.locked_until = now + timedelta(minutes=15)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check status
    if user.status != "active":
        reason_map = {
            "pending": "ACCOUNT_PENDING_APPROVAL",
            "suspended": "ACCOUNT_SUSPENDED",
            "rejected": "ACCOUNT_REJECTED",
        }
        reason_code = reason_map.get(user.status, "ACCOUNT_NOT_ACTIVE")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": reason_code, "status": user.status},
        )

    # Success: reset lockout
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login = now

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    # Touch identity last_used_at
    id_stmt = select(UserIdentity).where(UserIdentity.user_id == user.id, UserIdentity.provider == "password")
    id_res = await db.execute(id_stmt)
    pwd_identity = id_res.scalar_one_or_none()
    if pwd_identity:
        pwd_identity.last_used_at = now

    jwt_token = create_access_token(user_id=user.id, email=user.email, platform_role=user.platform_role)
    token_h = hash_token(jwt_token)
    expires_at = now + timedelta(hours=24)

    session_record = UserSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=token_h,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(session_record)
    await db.commit()

    return TokenResponse(
        access_token=jwt_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Change password for current authenticated user."""
    user_id = current_user.get("sub") or current_user.get("id")
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password login not configured for this account")

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current password incorrect")

    validate_password_policy(payload.new_password, user.email)

    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(payload.new_password)
    user.password_updated_at = now

    # Revoke all other sessions except current
    current_token = getattr(request.state, "token", None)
    if current_token:
        curr_hash = hash_token(current_token)
        sess_stmt = select(UserSession).where(UserSession.user_id == user.id, UserSession.token_hash != curr_hash)
        other_sessions = (await db.execute(sess_stmt)).scalars().all()
        for s in other_sessions:
            await db.delete(s)

    audit = AuditLog(
        id=str(uuid.uuid4()),
        actor_user_id=user.id,
        action="update",
        resource_type="user",
        resource_id=user.id,
        summary="User changed password",
        created_at=now,
    )
    db.add(audit)
    await db.commit()

    return {"status": "password_changed"}


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Initiate password reset flow. Returns non-enumerating 202."""
    norm_email = payload.email.strip().lower()

    # Generate dummy token to make execution time symmetric
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    stmt = select(User).where(User.email == norm_email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if user:
        now = datetime.now(timezone.utc)
        del_stmt = select(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        old_tokens = (await db.execute(del_stmt)).scalars().all()
        for t in old_tokens:
            await db.delete(t)

        settings = get_settings()
        ttl_minutes = getattr(settings, "PASSWORD_RESET_TTL_MINUTES", 30)

        reset_token = PasswordResetToken(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(minutes=ttl_minutes),
            created_at=now,
        )
        db.add(reset_token)
        await db.commit()

        public_url = getattr(settings, "APP_PUBLIC_URL", "http://localhost:5173")
        reset_url = f"{public_url}/auth/reset-password?token={raw_token}"
        logger.info(f"Password reset link generated for {norm_email}: {reset_url}")

    return {"status": "reset_email_sent"}


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Reset password using a single-use reset token."""
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    stmt = select(PasswordResetToken).where(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
    )
    res = await db.execute(stmt)
    reset_record = res.scalar_one_or_none()

    if not reset_record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    exp_utc = reset_record.expires_at.replace(tzinfo=timezone.utc) if reset_record.expires_at.tzinfo is None else reset_record.expires_at
    if exp_utc <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user = await db.get(User, reset_record.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    validate_password_policy(payload.new_password, user.email)

    user.password_hash = hash_password(payload.new_password)
    user.password_updated_at = now
    user.failed_login_count = 0
    user.locked_until = None
    reset_record.used_at = now

    sess_stmt = select(UserSession).where(UserSession.user_id == user.id)
    sessions = (await db.execute(sess_stmt)).scalars().all()
    for s in sessions:
        await db.delete(s)

    await db.commit()
    return {"status": "password_reset_success"}


