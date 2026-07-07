"""Lifespan factory for the FastAPI gateway.

Dynamically loads project submodules based on ACTIVE_PROJECTS setting.
Adapted from zypp_ai_monorepo/backend/core/setup.py.
"""

import importlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from common.config.settings import settings
from common.observability.logger import get_logger

logger = get_logger("gateway")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan — initializes and shuts down active projects.

    For each project in ACTIVE_PROJECTS:
    1. Imports projects.<name>.setup
    2. Calls init_app_state(app, settings) if it exists
    3. On shutdown, calls shutdown_app_state(app, settings) if it exists

    Projects without a setup.py are silently skipped.
    """
    # --- Startup phase ---
    for project in settings.ACTIVE_PROJECTS:
        module_path = f"projects.{project}.setup"
        try:
            module = importlib.import_module(module_path)
            if hasattr(module, "init_app_state"):
                await module.init_app_state(app, settings)
                logger.info("Initialized project: %s", project)
            else:
                logger.debug("No init_app_state in %s, skipping", project)
        except ModuleNotFoundError as e:
            if e.name == module_path:
                logger.debug("No setup.py for project: %s, skipping", project)
            else:
                logger.error(
                    "Missing dependency in %s (needs: %s): %s",
                    module_path, e.name, e,
                )
        except Exception as e:
            logger.error("Failed to initialize project %s: %s", project, e)

    logger.info("Gateway started with projects: %s", settings.ACTIVE_PROJECTS)
    yield

    # --- Shutdown phase ---
    for project in settings.ACTIVE_PROJECTS:
        module_path = f"projects.{project}.setup"
        try:
            module = importlib.import_module(module_path)
            if hasattr(module, "shutdown_app_state"):
                await module.shutdown_app_state(app, settings)
                logger.info("Shut down project: %s", project)
        except Exception as e:
            logger.error("Failed to shut down project %s: %s", project, e)
