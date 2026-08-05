"""External Provider Credentials API (S6).

Provides endpoints under `/api/settings/credentials` for platform admins to manage 
API keys for external providers (Google, OpenAI, Anthropic, OpenRouter, etc.).
Seamlessly loads environment fallback keys (.env) and allows DB overrides.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.postgres import get_async_db
from common.config.settings import get_settings
from common.models.database import ProviderCredential
from gateway.auth.dependencies import get_current_user

router = APIRouter(prefix="/settings/credentials", tags=["Credentials Management"])

ENV_PROVIDER_MAP = {
    "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "groq": ["GROQ_API_KEY"],
    "cerebras": ["CEREBRAS_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "mistral": ["MISTRAL_API_KEY"],
    "cohere": ["COHERE_API_KEY"],
    "huggingface": ["HF_TOKEN", "HUGGINGFACE_API_KEY", "HF_API_KEY"],
    "langsmith": ["LANGSMITH_API_KEY"],
}


def mask_key(key: str) -> str:
    """Return a masked representation of an API key for safe UI display."""
    if not key:
        return ""
    clean = key.strip()
    if len(clean) <= 8:
        return "****"
    return f"{clean[:4]}...{clean[-4:]}"


class CredentialBase(BaseModel):
    provider: str = Field(..., description="Provider identifier, e.g., 'google', 'openai', 'anthropic', 'openrouter'")
    api_key: str = Field(..., description="API Key value")


class CredentialResponse(BaseModel):
    id: str
    provider: str
    source: str = Field("db", description="'db' (database override) or 'env' (.env file / environment)")
    masked_key: str
    is_configured: bool = True
    created_at: datetime
    updated_at: datetime


class CredentialListResponse(BaseModel):
    items: List[CredentialResponse]


def require_admin(current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    """Dependency to ensure the current user is a platform admin."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if current_user.get("platform_role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admins can manage provider credentials",
        )
    return current_user


@router.get("", response_model=CredentialListResponse)
async def list_credentials(
    db: AsyncSession = Depends(get_async_db),
    _user: Dict[str, Any] = Depends(require_admin),
):
    """List all configured provider credentials from DB overrides and environment variables."""
    stmt = select(ProviderCredential)
    result = await db.execute(stmt)
    creds = result.scalars().all()

    items: List[CredentialResponse] = []
    seen_providers = set()

    # 1. DB Override Credentials
    for c in creds:
        p_name = c.provider.lower()
        seen_providers.add(p_name)
        items.append(
            CredentialResponse(
                id=f"db-{c.id}",
                provider=p_name,
                source="db",
                masked_key=mask_key(c.api_key),
                is_configured=True,
                created_at=c.created_at or datetime.now(timezone.utc).replace(tzinfo=None),
                updated_at=c.updated_at or datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )

    # 2. Environment Variable Fallbacks
    settings = get_settings()
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    for p_name, env_vars in ENV_PROVIDER_MAP.items():
        if p_name in seen_providers:
            continue

        for env_var in env_vars:
            val = os.getenv(env_var) or getattr(settings, env_var, None)
            if val and isinstance(val, str) and val.strip():
                items.append(
                    CredentialResponse(
                        id=f"env-{env_var}",
                        provider=p_name,
                        source="env",
                        masked_key=mask_key(val.strip()),
                        is_configured=True,
                        created_at=now_utc,
                        updated_at=now_utc,
                    )
                )
                seen_providers.add(p_name)
                break

    return CredentialListResponse(items=items)


@router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def upsert_credential(
    payload: CredentialBase,
    db: AsyncSession = Depends(get_async_db),
    _user: Dict[str, Any] = Depends(require_admin),
):
    """Add or update an API key for an external provider."""
    provider = payload.provider.lower()
    if provider == "gemini":
        provider = "google"

    # Sync into os.environ for active process execution
    env_vars = ENV_PROVIDER_MAP.get(provider, [f"{provider.upper()}_API_KEY"])
    for var in env_vars:
        os.environ[var] = payload.api_key.strip()

    # DB Persistence
    stmt = select(ProviderCredential).where(ProviderCredential.provider == provider)
    result = await db.execute(stmt)
    cred = result.scalar_one_or_none()

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    if cred:
        cred.api_key = payload.api_key.strip()
        cred.updated_at = now_naive
    else:
        cred = ProviderCredential(
            provider=provider,
            api_key=payload.api_key.strip(),
            created_at=now_naive,
            updated_at=now_naive,
        )
        db.add(cred)

    try:
        await db.commit()
        await db.refresh(cred)
        return CredentialResponse(
            id=f"db-{cred.id}",
            provider=cred.provider,
            source="db",
            masked_key=mask_key(cred.api_key),
            is_configured=True,
            created_at=cred.created_at or now_naive,
            updated_at=cred.updated_at or now_naive,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_credential(
    provider: str,
    db: AsyncSession = Depends(get_async_db),
    _user: Dict[str, Any] = Depends(require_admin),
):
    """Remove an API key for a provider."""
    provider = provider.lower()
    if provider == "gemini":
        provider = "google"

    # Remove from os.environ
    env_vars = ENV_PROVIDER_MAP.get(provider, [f"{provider.upper()}_API_KEY"])
    for var in env_vars:
        os.environ.pop(var, None)

    stmt = select(ProviderCredential).where(ProviderCredential.provider == provider)
    result = await db.execute(stmt)
    cred = result.scalar_one_or_none()

    if cred:
        await db.delete(cred)
        await db.commit()
