"""Dynamic API router discovery.

Automatically discovers and includes project API routers based on ACTIVE_PROJECTS.
Adapted from zypp_ai_monorepo/backend/api/__init__.py.
"""

import importlib
from pathlib import Path
from typing import Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException, Request, WebSocket, status

from common.config.settings import settings
from common.observability.logger import get_logger, log_security_event
from common.clients.postgres import get_sessionmaker
from common.models.database import APIKeyModel
from sqlalchemy import select

logger = get_logger("gateway.api")

BASE_DIR = Path(__file__).resolve().parents[2]
PROJECTS_DIR = BASE_DIR / "projects"


async def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> None:
    """Verifies that the request provides valid auth: JWT session OR active API key when AUTH_ENABLED is True."""
    if not settings.AUTH_ENABLED:
        return

    path = request.url.path
    if (
        path.startswith("/api/qdrant")
        or path.startswith("/api/neo4j")
        or path.startswith("/api/telemetry")
    ):
        return

    # 1. If user is already authenticated via JWT session, allow request
    if getattr(request.state, "user", None):
        return

    # 2. If X-API-Key header is provided, validate hashed key against DB
    if x_api_key:
        from gateway.api.api_keys import hash_api_key
        hashed_key = hash_api_key(x_api_key)

        session_factory = get_sessionmaker()
        async with session_factory() as session:
            key_record = await session.scalar(
                select(APIKeyModel)
                .where((APIKeyModel.key == hashed_key) | (APIKeyModel.key == x_api_key))
                .where(APIKeyModel.is_active == True)
            )
            if key_record:
                # Update usage tracking
                key_record.usage_count = (key_record.usage_count or 0) + 1
                await session.commit()
                return

    # 3. Log security failure and reject with 401
    log_security_event(
        event_type="UNAUTHORIZED_ACCESS_ATTEMPT",
        details={
            "path": path,
            "method": request.method,
            "has_api_key": bool(x_api_key),
            "reason": "Missing or invalid authentication credentials",
        },
    )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Missing authentication credentials or X-API-Key header"
    )


router = APIRouter(prefix="/api", dependencies=[Depends(verify_api_key)])
public_router = APIRouter(prefix="/api")

from gateway.api.hubs import router as hubs_router
from gateway.api.ingestion_hub import router as ingestion_hub_router
from gateway.api.workflows import router as workflows_router
from gateway.api.eval_hub import router as eval_hub_router
from gateway.api.admin_audit import router as admin_audit_router
from gateway.api.admin_users import router as admin_users_router
from gateway.api.models import router as models_router
from gateway.api.agent_crud import router as agent_crud_router
from gateway.api.telemetry import router as telemetry_router
from gateway.api.agent_invoke import router as agent_invoke_router
from gateway.api.playground import router as playground_router
from gateway.api.mcp_manager import router as mcp_manager_router
from gateway.api.api_keys import router as api_keys_router
from gateway.api.proxy import router as proxy_router
from gateway.api.credentials import router as credentials_router
from gateway.api.db_credentials import router as db_credentials_router

from gateway.api.health import router as health_router

public_router.include_router(telemetry_router)
public_router.include_router(health_router)

router.include_router(hubs_router)
router.include_router(ingestion_hub_router)
router.include_router(workflows_router)
router.include_router(eval_hub_router)
router.include_router(admin_audit_router)
router.include_router(admin_users_router)
router.include_router(models_router)
router.include_router(agent_crud_router)
router.include_router(telemetry_router)
router.include_router(agent_invoke_router)
router.include_router(playground_router)
router.include_router(mcp_manager_router)
router.include_router(api_keys_router)
router.include_router(proxy_router)
router.include_router(credentials_router)
router.include_router(db_credentials_router)

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
