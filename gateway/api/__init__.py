"""Dynamic API router discovery.

Automatically discovers and includes project API routers based on ACTIVE_PROJECTS.
Adapted from zypp_ai_monorepo/backend/api/__init__.py.
"""

import importlib
from pathlib import Path

from fastapi import APIRouter

from common.config.settings import settings
from common.observability.logger import get_logger

logger = get_logger("gateway.api")

BASE_DIR = Path(__file__).resolve().parents[2]
PROJECTS_DIR = BASE_DIR / "projects"

router = APIRouter(prefix="/api")

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
