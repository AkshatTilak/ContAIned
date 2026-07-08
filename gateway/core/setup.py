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
    # 1. Verify database connections on startup (if not in testing mode)
    if settings.APP_ENV != "testing":
        try:
            from common.clients.postgres import verify_connection_with_retry
            logger.info("Verifying PostgreSQL connection...")
            await verify_connection_with_retry()
        except Exception as e:
            logger.critical("Database verification failed: %s", e)
            raise e

        try:
            import asyncio
            from alembic.config import Config
            from alembic import command
            logger.info("Running database migrations via Alembic...")
            alembic_cfg = Config("alembic.ini")
            await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
            logger.info("Database migrations completed successfully.")
        except Exception as e:
            logger.critical("Failed to run database migrations: %s", e)
            raise e

        try:
            from common.clients.redis import verify_redis_connection
            logger.info("Verifying Redis connection...")
            await verify_redis_connection()
        except Exception as e:
            logger.warning("Redis verification failed (continuing in degraded state): %s", e)

        try:
            from common.clients.neo4j import verify_neo4j_connection
            logger.info("Verifying Neo4j connection...")
            await verify_neo4j_connection()
        except Exception as e:
            logger.warning("Neo4j verification failed (continuing in degraded state): %s", e)

    # 2. Initialize and seed Model Registry
    try:
        from common.models.registry import init_model_registry
        await init_model_registry()
        logger.info("Model registry initialized and seeded.")
    except Exception as e:
        logger.error("Failed to initialize model registry: %s", e)

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

    # Close shared clients connections
    try:
        from common.clients.redis import close_redis
        await close_redis()
    except Exception as e:
        logger.error("Failed to close Redis connection on shutdown: %s", e)

    try:
        from common.clients.neo4j import close_neo4j
        await close_neo4j()
    except Exception as e:
        logger.error("Failed to close Neo4j connection on shutdown: %s", e)
