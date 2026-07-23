"""Dynamic API router discovery.

Automatically discovers and includes project API routers based on ACTIVE_PROJECTS.
Adapted from zypp_ai_monorepo/backend/api/__init__.py.
"""

import importlib
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from common.config.settings import settings
from common.observability.logger import get_logger, log_security_event
from common.clients.postgres import get_sessionmaker
from common.models.database import APIKeyModel
from sqlalchemy import select

logger = get_logger("gateway.api")

BASE_DIR = Path(__file__).resolve().parents[2]
PROJECTS_DIR = BASE_DIR / "projects"


async def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    """Verifies that the request provides a valid active API key when AUTH_ENABLED is True."""
    if not settings.AUTH_ENABLED:
        return

    if not x_api_key:
        log_security_event("AUTH_FAILURE", {"reason": "Missing X-API-Key header"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing X-API-Key header"
        )

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        result = await session.execute(
            select(APIKeyModel)
            .where(APIKeyModel.key == x_api_key)
            .where(APIKeyModel.is_active == True)
        )
        db_key = result.scalar_one_or_none()
        if not db_key:
            log_security_event("AUTH_FAILURE", {"reason": "Invalid or inactive X-API-Key", "provided_key": x_api_key})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Invalid X-API-Key"
            )


router = APIRouter(prefix="/api", dependencies=[Depends(verify_api_key)])

from gateway.api.models import router as models_router
from gateway.api.agent_crud import router as agent_crud_router
from gateway.api.telemetry import router as telemetry_router
from gateway.api.agent_invoke import router as agent_invoke_router
from gateway.api.playground import router as playground_router
from gateway.api.mcp_manager import router as mcp_manager_router
from gateway.api.api_keys import router as api_keys_router

router.include_router(models_router)
router.include_router(agent_crud_router)
router.include_router(telemetry_router)
router.include_router(agent_invoke_router)
router.include_router(playground_router)
router.include_router(mcp_manager_router)
router.include_router(api_keys_router)

# Dynamically load project API routers
# Make changes in .env ACTIVE_PROJECTS to register/deregister projects.
for project in settings.ACTIVE_PROJECTS:
    project_dir = PROJECTS_DIR / project
    if project_dir.exists():
        try:
            module = importlib.import_module(f"projects.{project}.api")
            if hasattr(module, "router"):
                router.include_router(module.router, prefix=f"/{project}")
                logger.info("Loaded API routes for: %s", project)
            else:
                logger.debug("No router in projects.%s.api, skipping", project)
        except ModuleNotFoundError as e:
            if e.name == f"projects.{project}.api":
                logger.debug("No api.py for project: %s, skipping", project)
            else:
                logger.error("Missing dep loading %s routes: %s", project, e)
        except Exception as e:
            logger.error("Failed to load %s routes: %s", project, e)
    else:
        logger.warning("Project directory not found: %s", project_dir)
