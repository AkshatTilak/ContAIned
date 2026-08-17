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
            logger.warning("Alembic auto-migration check skipped/failed (continuing startup): %s", e)

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

        try:
            from common.clients.qdrant import VectorClient
            logger.info("Verifying Qdrant connection...")
            qdrant_client = VectorClient()
            await qdrant_client.verify_connection()
        except Exception as e:
            logger.warning("Qdrant verification failed (continuing in degraded state): %s", e)

        try:
            import socket
            host, port = settings.KAFKA_BOOTSTRAP_SERVERS.split(":")[0], int(settings.KAFKA_BOOTSTRAP_SERVERS.split(":")[1]) if ":" in settings.KAFKA_BOOTSTRAP_SERVERS else 9092
            with socket.create_connection((host, port), timeout=0.2):
                from confluent_kafka.admin import AdminClient
                logger.info("Verifying Kafka connection...")
                conf = {"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS, "socket.timeout.ms": 2000}
                admin_client = AdminClient(conf)
                await asyncio.to_thread(admin_client.list_topics, timeout=2.0)
                logger.info("Kafka connection verified successfully.")
        except Exception:
            logger.info("Kafka broker (%s) is not reachable. Skipping Kafka setup (running in local fallback mode).", settings.KAFKA_BOOTSTRAP_SERVERS)

    # 2. Initialize and seed Model Registry
    try:
        from common.models.registry import init_model_registry
        await init_model_registry()
        logger.info("Model registry initialized and seeded.")
    except Exception as e:
        logger.error("Failed to initialize model registry: %s", e)

    # Seed default API key if empty
    try:
        from common.clients.postgres import get_sessionmaker
        from common.models.database import APIKeyModel, User, UserIdentity
        from gateway.auth.passwords import hash_password, verify_password
        from gateway.auth.utils import normalize_email
        from sqlalchemy import select
        import uuid
        from datetime import datetime

        session_factory = get_sessionmaker()
        async with session_factory() as session:
            res = await session.execute(select(APIKeyModel).limit(1))
            if not res.scalars().first():
                default_key = APIKeyModel(
                    key="sk_live_default_key",
                    name="default-dev-key",
                    is_active=True
                )
                session.add(default_key)
                await session.commit()
                logger.info("Database API keys table seeded with default key 'sk_live_default_key'.")

            # Ensure local-admin-id user row exists in PostgreSQL for API key / local dev operations
            res_admin_user = await session.execute(select(User).where(User.id == "local-admin-id"))
            if not res_admin_user.scalar_one_or_none():
                now_admin = datetime.utcnow()
                local_admin = User(
                    id="local-admin-id",
                    email="admin@contained.local",
                    display_name="API Key Admin",
                    platform_role="admin",
                    status="active",
                    created_at=now_admin,
                )
                session.add(local_admin)
                await session.commit()
                logger.info("Seeded local admin user record (local-admin-id).")

            async def reconcile_bootstrap_account(
                email: str | None,
                password: str | None,
                *,
                display_name: str,
                platform_role: str,
            ) -> None:
                """Make configured bootstrap credentials authoritative on every startup."""
                if not email or not password:
                    return

                normalized_email = normalize_email(email)
                result = await session.execute(select(User).where(User.email == normalized_email))
                user = result.scalar_one_or_none()
                now = datetime.utcnow()

                if user is None:
                    user = User(
                        id=str(uuid.uuid4()),
                        email=normalized_email,
                        display_name=display_name,
                        platform_role=platform_role,
                        status="active",
                        password_hash=hash_password(password),
                        password_updated_at=now,
                        created_at=now,
                    )
                    session.add(user)
                    await session.flush()
                    logger.info("Created environment bootstrap account: %s", normalized_email)
                else:
                    user.display_name = user.display_name or display_name
                    user.platform_role = platform_role
                    user.status = "active"
                    user.is_deleted = False
                    user.deleted_at = None
                    user.failed_login_count = 0
                    user.locked_until = None
                    if not verify_password(password, user.password_hash):
                        user.password_hash = hash_password(password)
                        user.password_updated_at = now
                    logger.info("Reconciled environment bootstrap account: %s", normalized_email)

                identity_result = await session.execute(
                    select(UserIdentity).where(
                        UserIdentity.user_id == user.id,
                        UserIdentity.provider == "password",
                    )
                )
                if identity_result.scalar_one_or_none() is None:
                    session.add(
                        UserIdentity(
                            id=str(uuid.uuid4()),
                            user_id=user.id,
                            provider="password",
                            provider_id=user.id,
                            email=normalized_email,
                            created_at=now,
                        )
                    )

                await session.commit()

            await reconcile_bootstrap_account(
                getattr(settings, "ADMIN_EMAIL", None),
                getattr(settings, "ADMIN_PASSWORD", None),
                display_name="Admin",
                platform_role="admin",
            )
            await reconcile_bootstrap_account(
                getattr(settings, "TEST_USER_EMAIL", None),
                getattr(settings, "TEST_USER_PASSWORD", None),
                display_name="Automated Test User",
                platform_role="member",
            )

    except Exception as e:
        logger.error("Failed to seed default API key / bootstrap admin accounts: %s", e)

    # Auto-register SyntraFlow internal MCP server (S5-05d)
    try:
        from common.clients.postgres import get_sessionmaker
        from gateway.api.mcp_manager import register_mcp_server
        session_factory = get_sessionmaker()
        async with session_factory() as session:
            syntraflow_url = getattr(settings, "MCP_SYNTRAFLOW_URL", "http://localhost:8012")
            await register_mcp_server(
                session=session,
                name="SyntraFlow (Internal)",
                url=syntraflow_url,
                transport="sse",
                auth_type="none",
                is_internal=True
            )
            logger.info("Auto-registered SyntraFlow internal MCP server.")
    except Exception as e:
        logger.error("Failed to auto-register internal SyntraFlow MCP server: %s", e)

    # Reconcile orphaned workflow runs left in queued/running state on startup (S6-06d)
    try:
        from common.clients.postgres import get_sessionmaker
        from projects.guardroute.src.workflows.run_service import reconcile_orphaned_runs
        session_factory = get_sessionmaker()
        async with session_factory() as session:
            count = await reconcile_orphaned_runs(session)
            if count > 0:
                logger.info("Reconciled %d orphaned workflow run(s) left from previous process.", count)
    except Exception as e:
        logger.error("Failed to reconcile orphaned workflow runs: %s", e)

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

    # Start periodic background task for sweeping expired invites (every 15 min)
    sweeper_task = None
    if settings.APP_ENV != "testing":
        import asyncio

        async def _periodic_invite_sweeper():
            from common.clients.postgres import get_sessionmaker
            from gateway.auth.invites import sweep_expired_invites
            session_factory = get_sessionmaker()
            while True:
                try:
                    await asyncio.sleep(900)  # 15 minutes
                    async with session_factory() as session:
                        await sweep_expired_invites(session)
                except asyncio.CancelledError:
                    break
                except Exception as ex:
                    logger.error("Error in periodic invite sweeper: %s", ex)
                    await asyncio.sleep(60)

        sweeper_task = asyncio.create_task(_periodic_invite_sweeper())

    logger.info("Gateway started with projects: %s", settings.ACTIVE_PROJECTS)
    yield

    # --- Shutdown phase ---
    if sweeper_task:
        sweeper_task.cancel()

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

    try:
        from common.clients.postgres import close_postgres
        await close_postgres()
    except Exception as e:
        logger.error("Failed to close Postgres engine on shutdown: %s", e)
