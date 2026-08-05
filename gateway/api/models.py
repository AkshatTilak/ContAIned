"""Model Registry API endpoints for the gateway."""

import os
import shutil
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import httpx
import litellm
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.postgres import get_async_db
from common.config.settings import settings
from common.models.database import ModelRegistryModel, ProviderCredential
from common.models.registry import list_available, get_active_model

router = APIRouter(prefix="/models", tags=["models"])
logger = logging.getLogger("gateway.api.models")


class ModelSelectRequest(BaseModel):
    role: str
    model_id: str


class ModelRegisterRequest(BaseModel):
    role: str = Field(..., description="'ocr' | 'asr' | 'embedding' | 'classifier' | 'completion'")
    mode: str = Field("cloud", description="'local' | 'cloud'")
    provider: str = Field(..., description="e.g. 'google', 'openai', 'groq', 'anthropic'")
    model_id: str = Field(..., description="The unique litellm/local identifier")
    display_name: str = Field(..., description="Human readable model name")
    framework: Optional[str] = "litellm"
    vram_mb: Optional[int] = 0
    vector_dim: Optional[int] = None
    context_window: Optional[int] = None
    is_default: Optional[bool] = False
    is_enabled: Optional[bool] = True
    priority: Optional[int] = 0


class ModelUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    mode: Optional[str] = None
    provider: Optional[str] = None
    framework: Optional[str] = None
    vram_mb: Optional[int] = None
    vector_dim: Optional[int] = None
    context_window: Optional[int] = None
    is_default: Optional[bool] = None
    is_enabled: Optional[bool] = None
    priority: Optional[int] = None


LITELLM_PROVIDER_MAP = {
    "google": ["gemini"],
    "gemini": ["gemini"],
    "openai": ["openai"],
    "openrouter": ["openrouter"],
    "groq": ["groq"],
    "anthropic": ["anthropic"],
    "cerebras": ["cerebras"],
    "mistral": ["mistral"],
    "cohere": ["cohere", "cohere_chat"],
    "xai": ["xai"],
}


@router.get("")
@router.get("/")
@router.get("/registry")
async def get_full_registry(db: AsyncSession = Depends(get_async_db)) -> dict:
    """Fetch all models in the database registry grouped by role, indicating active status."""
    try:
        # Check database provider keys first
        stmt = select(ProviderCredential.provider)
        db_keys_res = await db.execute(stmt)
        db_keys = {row[0] for row in db_keys_res}

        has_openai = "openai" in db_keys or bool(settings.OPENAI_API_KEY)
        has_gemini = "gemini" in db_keys or bool(settings.GOOGLE_API_KEY)
        has_anthropic = "anthropic" in db_keys or bool(getattr(settings, "ANTHROPIC_API_KEY", None))
        has_openrouter = "openrouter" in db_keys or bool(settings.OPENROUTER_API_KEY)
        has_groq = "groq" in db_keys or bool(settings.GROQ_API_KEY)

        provider_keys = {
            "openai": has_openai,
            "gemini": has_gemini,
            "google": has_gemini,
            "anthropic": has_anthropic,
            "openrouter": has_openrouter,
            "groq": has_groq,
        }

        roles = ["ocr", "asr", "embedding", "classifier", "completion"]
        registry_data = {}
        for role in roles:
            available = await list_available(role, db=db)
            try:
                active = await get_active_model(role, db=db)
                active_dump = active.model_dump(mode="json") if active else None
            except Exception as e:
                logger.warning("No active model resolved for role %s: %s", role, e)
                active_dump = None
                
            avail_dumps = []
            for m in available:
                m_dump = m.model_dump(mode="json")
                if m.mode == "local":
                    m_dump["is_selectable"] = True
                    m_dump["status_flag"] = "local_only"
                else:
                    is_avail = provider_keys.get(m.provider.lower(), False)
                    m_dump["is_selectable"] = is_avail
                    m_dump["status_flag"] = "ready" if is_avail else "missing_key"
                avail_dumps.append(m_dump)

            registry_data[role] = {
                "active": active_dump,
                "available": avail_dumps
            }
        return registry_data
    except Exception as e:
        logger.error("Error in get_full_registry: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch model registry: {str(e)}")


@router.post("")
@router.post("/register")
async def register_model(req: ModelRegisterRequest, db: AsyncSession = Depends(get_async_db)) -> dict:
    """Register a new custom model in the database model registry."""
    # Check if duplicate exists
    stmt = select(ModelRegistryModel).where(
        ModelRegistryModel.role == req.role,
        ModelRegistryModel.model_id == req.model_id
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Model '{req.model_id}' is already registered under role '{req.role}'."
        )

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    model_entry = ModelRegistryModel(
        role=req.role.lower(),
        mode=req.mode.lower(),
        provider=req.provider.lower(),
        model_id=req.model_id,
        display_name=req.display_name,
        framework=req.framework,
        vram_mb=req.vram_mb,
        vector_dim=req.vector_dim,
        context_window=req.context_window,
        is_default=req.is_default,
        is_enabled=req.is_enabled,
        priority=req.priority,
        created_at=now_naive,
    )

    if req.is_default:
        # Reset other default models for this role
        await db.execute(
            update(ModelRegistryModel)
            .where(ModelRegistryModel.role == req.role.lower())
            .values(is_default=False)
        )

    db.add(model_entry)
    try:
        await db.commit()
        await db.refresh(model_entry)
        return {
            "status": "success",
            "message": f"Successfully registered {req.display_name} in model registry.",
            "model": {
                "id": model_entry.id,
                "model_id": model_entry.model_id,
                "role": model_entry.role,
                "provider": model_entry.provider,
                "is_default": model_entry.is_default,
            }
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database failed: {str(e)}"
        )


@router.put("/{model_id:path}")
async def update_registered_model(
    model_id: str,
    req: ModelUpdateRequest,
    db: AsyncSession = Depends(get_async_db)
) -> dict:
    """Update a model configuration in the registry."""
    stmt = select(ModelRegistryModel).where(ModelRegistryModel.model_id == model_id)
    result = await db.execute(stmt)
    model_entry = result.scalar_one_or_none()
    if not model_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found in registry."
        )

    for field, val in req.model_dump(exclude_unset=True).items():
        setattr(model_entry, field, val)

    if req.is_default:
        # Reset other default models for this role
        await db.execute(
            update(ModelRegistryModel)
            .where(ModelRegistryModel.role == model_entry.role)
            .values(is_default=False)
        )
        model_entry.is_default = True

    try:
        await db.commit()
        return {"status": "success", "message": f"Updated model {model_id}."}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{model_id:path}")
async def delete_registered_model(model_id: str, db: AsyncSession = Depends(get_async_db)) -> dict:
    """Delete a registered model configuration."""
    stmt = select(ModelRegistryModel).where(ModelRegistryModel.model_id == model_id)
    result = await db.execute(stmt)
    model_entry = result.scalar_one_or_none()
    if not model_entry:
        raise HTTPException(status_code=404, detail="Model not found in registry")

    await db.delete(model_entry)
    await db.commit()
    return {"status": "success", "message": f"Deleted model {model_id} from registry."}


@router.get("/litellm/available")
async def get_litellm_available_models(provider: str) -> dict:
    """Fetch available models and their type modes for a given provider from LiteLLM registry."""
    prov_lower = provider.lower()
    lite_keys = LITELLM_PROVIDER_MAP.get(prov_lower, [prov_lower])

    models = []
    for k in lite_keys:
        prov_models = litellm.models_by_provider.get(k, [])
        for m in prov_models:
            # Prevent duplicates
            if any(x["name"] == m for x in models):
                continue
            try:
                info = litellm.get_model_info(m)
                mode = info.get("mode", "chat")
            except Exception:
                # Deduce fallback mode based on keywords
                mode = "embedding" if "embed" in m.lower() else "chat"
            models.append({"name": m, "mode": mode})

    return {"items": models}


@router.post("/select")
async def select_active_model(req: ModelSelectRequest, db: AsyncSession = Depends(get_async_db)) -> dict:
    """Toggle the active/default model for a specific role in the database."""
    role = req.role.lower()
    model_id = req.model_id
    
    valid_roles = {"ocr", "asr", "embedding", "classifier", "completion"}
    if role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model role: '{role}'. Must be one of: {list(valid_roles)}",
        )
        
    # Check if the model exists and is enabled
    stmt = select(ModelRegistryModel).where(
        ModelRegistryModel.role == role,
        ModelRegistryModel.model_id == model_id,
        ModelRegistryModel.is_enabled == True
    )
    result = await db.execute(stmt)
    model_entry = result.scalar_one_or_none()
    if not model_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Enabled model '{model_id}' not found for role '{role}' in registry.",
        )
        
    try:
        # Reset all default flags for this role
        await db.execute(
            update(ModelRegistryModel)
            .where(ModelRegistryModel.role == role)
            .values(is_default=False)
        )
        # Set this model as default
        model_entry.is_default = True
        await db.commit()
        logger.info("Updated default model for role %s to %s", role, model_id)
    except Exception as e:
        await db.rollback()
        logger.error("Failed to update default model: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update database default model: {str(e)}"
        )
        
    # Notify inference server to reload registry loaders dynamically if it is online
    inference_reloaded = False
    reload_message = "Local default updated in DB."
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{settings.INFERENCE_SERVER_URL.rstrip('/')}/reload")
            if resp.status_code == 200:
                inference_reloaded = True
                reload_message = "Model registry default updated and loaders hot-reloaded on inference server."
                logger.info("Inference server reloaded model loaders successfully.")
            else:
                reload_message = f"Registry updated in DB but inference server reload returned status {resp.status_code}."
                logger.warning("Inference server reload failed: %s", resp.text)
    except Exception as e:
        reload_message = f"Registry updated in DB but failed to notify inference server (offline): {str(e)}"
        logger.warning("Failed to contact inference server for reload: %s", e)
        
    return {
        "status": "success",
        "message": reload_message,
        "inference_reloaded": inference_reloaded,
        "selected": {
            "role": role,
            "model_id": model_id,
            "display_name": model_entry.display_name
        }
    }


def resolve_local_model_disk_info(model_id: str, framework: Optional[str] = None) -> dict:
    """Resolve expected local disk path and check if model artifacts exist."""
    hf_home = os.path.expanduser(os.environ.get("HF_HOME", "~/.cache/huggingface/hub"))
    workspace_models = os.path.abspath("models")
    
    # 1. GGUF / local workspace model check
    if model_id.endswith(".gguf") or (framework and "llama-cpp" in framework.lower()) or "arch-router" in model_id.lower():
        gguf_name = "Arch-Router-1.5B-Q8_0.gguf" if "arch-router" in model_id.lower() else model_id
        target_path = os.path.join(workspace_models, gguf_name)
        return {
            "local_path": target_path,
            "is_downloaded": os.path.exists(target_path)
        }
        
    # 2. Harrier model check (uses BAAI/bge-base-en-v1.5)
    if "harrier" in model_id.lower():
        target_path = os.path.join(hf_home, "models--BAAI--bge-base-en-v1.5")
        return {
            "local_path": target_path,
            "is_downloaded": os.path.exists(target_path)
        }
        
    # 3. Standard HuggingFace repo path
    clean_id = model_id.replace("/", "--")
    target_path = os.path.join(hf_home, f"models--{clean_id}")
    return {
        "local_path": target_path,
        "is_downloaded": os.path.exists(target_path)
    }


@router.get("/local/status")
async def get_local_models_status(db: AsyncSession = Depends(get_async_db)) -> dict:
    """Fetch status of all local models, combining DB config with live inference status and local disk existence."""
    stmt = select(ModelRegistryModel).where(ModelRegistryModel.mode == "local")
    result = await db.execute(stmt)
    local_models = result.scalars().all()
    
    loaded_models = []
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.INFERENCE_SERVER_URL.rstrip('/')}/health")
            if resp.status_code == 200:
                data = resp.json()
                raw_loaded = data.get("loaded_models") or data.get("vram", {}).get("loaded_models", [])
                loaded_models = [m.get("name") if isinstance(m, dict) else str(m) for m in raw_loaded]
    except Exception as e:
        logger.warning(f"Could not reach inference server for local status: {e}")
        
    loaded_lower = [lm.lower() for lm in loaded_models]
    status_list = []
    for m in local_models:
        disk_info = resolve_local_model_disk_info(m.model_id, m.framework)
        is_running = (
            m.model_id in loaded_models or
            m.model_id.lower() in loaded_lower or
            m.display_name.lower() in loaded_lower
        )
        status_list.append({
            "id": m.id,
            "model_id": m.model_id,
            "display_name": m.display_name,
            "role": m.role,
            "vram_mb": m.vram_mb,
            "is_enabled": m.is_enabled,
            "is_running": is_running,
            "local_path": disk_info["local_path"],
            "is_downloaded": disk_info["is_downloaded"],
        })
        
    return {"items": status_list}


@router.post("/local/{model_id}/start")
async def start_local_model(model_id: str) -> dict:
    """Proxy command to start/load a local model on inference server."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{settings.INFERENCE_SERVER_URL.rstrip('/')}/models/{model_id}/load")
            if resp.status_code == 200:
                return resp.json()
            else:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reach inference server: {str(e)}")


@router.post("/local/{model_id}/stop")
async def stop_local_model(model_id: str) -> dict:
    """Proxy command to stop/unload a local model on inference server."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{settings.INFERENCE_SERVER_URL.rstrip('/')}/models/{model_id}/unload")
            if resp.status_code == 200:
                return resp.json()
            else:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reach inference server: {str(e)}")


@router.delete("/local/{model_id:path}")
async def delete_local_model(
    model_id: str,
    purge_disk: bool = False,
    db: AsyncSession = Depends(get_async_db)
) -> dict:
    """Unload model from VRAM, optionally delete cached files from disk, and remove from registry."""
    # 1. Stop/unload model if running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{settings.INFERENCE_SERVER_URL.rstrip('/')}/models/{model_id}/unload")
    except Exception as e:
        logger.warning(f"Could not reach inference server to unload model '{model_id}': {e}")

    # 2. Purge local disk files if requested
    disk_purged = False
    if purge_disk:
        disk_info = resolve_local_model_disk_info(model_id)
        path = disk_info.get("local_path")
        if path and os.path.exists(path):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                disk_purged = True
                logger.info(f"Purged local disk files for model '{model_id}' at {path}")
            except Exception as e:
                logger.error(f"Failed to delete local disk files at {path}: {e}")

    # 3. Delete from model_registry DB table
    stmt = select(ModelRegistryModel).where(
        ModelRegistryModel.model_id == model_id,
        ModelRegistryModel.mode == "local"
    )
    result = await db.execute(stmt)
    model_entry = result.scalar_one_or_none()
    if model_entry:
        await db.delete(model_entry)
        await db.commit()

    return {
        "status": "success",
        "message": f"Successfully deleted model '{model_id}' from registry.",
        "disk_purged": disk_purged
    }
