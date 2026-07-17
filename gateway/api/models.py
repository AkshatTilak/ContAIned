"""Model Registry API endpoints for the gateway."""

import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.clients.postgres import get_async_db
from common.config.settings import settings
from common.models.database import ModelRegistryModel
from common.models.registry import list_available, get_active_model

router = APIRouter(prefix="/models", tags=["models"])
logger = logging.getLogger("gateway.api.models")


class ModelSelectRequest(BaseModel):
    role: str
    model_id: str


@router.get("/registry")
async def get_full_registry(db: AsyncSession = Depends(get_async_db)) -> dict:
    """Fetch all models in the database registry grouped by role, indicating active status."""
    roles = ["ocr", "asr", "embedding", "classifier", "completion"]
    registry_data = {}
    for role in roles:
        available = await list_available(role, db=db)
        try:
            active = await get_active_model(role, db=db)
            active_dump = active.model_dump() if active else None
        except Exception as e:
            logger.warning("No active model resolved for role %s: %s", role, e)
            active_dump = None
            
        registry_data[role] = {
            "active": active_dump,
            "available": [m.model_dump() for m in available]
        }
    return registry_data


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
