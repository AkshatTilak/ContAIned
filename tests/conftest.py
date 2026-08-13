"""Root pytest conftest for ContAIned platform test suite.

Loads `.env.test` settings, registers custom markers, manages ephemeral real-service connections,
provides factory fixtures, process management, and structured test logging.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Callable

import httpx
import pytest
from dotenv import load_dotenv

# Ensure .env.test is loaded before settings initialization
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_TEST = ROOT_DIR / ".env.test"
if ENV_TEST.exists():
    load_dotenv(dotenv_path=ENV_TEST, override=True)
else:
    ENV_TEST_EXAMPLE = ROOT_DIR / ".env.test.example"
    if ENV_TEST_EXAMPLE.exists():
        load_dotenv(dotenv_path=ENV_TEST_EXAMPLE, override=True)

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from common.config.settings import settings
from common.clients.postgres import get_async_db
from gateway.main import app as gateway_app

logger = logging.getLogger("tests.conftest")

# Log Directory setup
LOG_DIR = ROOT_DIR / "tests" / "logs" / datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "test_run.jsonl"


def pytest_configure(config):
    """Configure pytest markers and environment defaults."""
    config.addinivalue_line("markers", "unit: Fast mock-based unit tests with no external I/O")
    config.addinivalue_line("markers", "integration: Real service integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end multi-step workflow tests")
    config.addinivalue_line("markers", "live_api: External live API tests (Google Gemini, LiteLLM)")
    config.addinivalue_line("markers", "streaming: WebSocket and SSE streaming tests")
    config.addinivalue_line("markers", "performance: Performance and benchmark tests")


@pytest.fixture(scope="session")
def event_loop():
    """Create session-wide event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings():
    """Expose global environment settings instance."""
    return settings


# ──────────────────────────────────────────────
# Real Service Database Fixtures
# ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_engine():
    """Session-scoped SQLAlchemy engine connecting to test database."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture(scope="session")
def test_sessionmaker(test_engine):
    """Session-scoped AsyncSession factory."""
    return async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )


@pytest.fixture
async def real_db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Async session fixture wrapping each test in a transaction and rolling back."""
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture
async def qdrant_client():
    """Qdrant client fixture for vector store integration tests."""
    try:
        from qdrant_client import AsyncQdrantClient
        client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=10.0)
        yield client
        await client.close()
    except Exception as e:
        logger.warning(f"Qdrant client fixture initialized in fallback mode: {e}")
        yield None


@pytest.fixture
async def redis_client():
    """Redis async client fixture."""
    try:
        import redis.asyncio as redis
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        yield client
        await client.close()
    except Exception as e:
        logger.warning(f"Redis client fixture initialized in fallback mode: {e}")
        yield None


@pytest.fixture
async def neo4j_driver():
    """Neo4j async driver fixture."""
    try:
        from neo4j import AsyncGraphDatabase
        driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URL,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        yield driver
        await driver.close()
    except Exception as e:
        logger.warning(f"Neo4j driver fixture initialized in fallback mode: {e}")
        yield None


@pytest.fixture
async def gateway_client(real_db_session) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client fixture with database dependency override against Gateway ASGI app."""
    async def override_get_db():
        yield real_db_session

    gateway_app.dependency_overrides[get_async_db] = override_get_db
    transport = httpx.ASGITransport(app=gateway_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    gateway_app.dependency_overrides.clear()


# ──────────────────────────────────────────────
# Factory Fixture Chain (User -> Hub -> Workflow)
# ──────────────────────────────────────────────

@pytest.fixture
async def seed_user(real_db_session) -> Callable:
    """Factory fixture to create test users in DB."""
    from common.models.user import User
    from common.security.passwords import hash_password

    async def _create_user(
        email: str = "test_user_seed@contained.ai",
        full_name: str = "Seed Test User",
        role: str = "admin",
        password: str = "TestPass123!"
    ) -> User:
        user = User(
            email=email,
            full_name=full_name,
            role=role,
            password_hash=hash_password(password),
            is_active=True,
            is_approved=True,
        )
        real_db_session.add(user)
        await real_db_session.flush()
        await real_db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
async def seed_hub(real_db_session, seed_user) -> Callable:
    """Factory fixture to create test hubs linked to user."""
    from common.models.hub import Hub, HubMember

    async def _create_hub(owner=None, name: str = "Seed Test Hub", slug: str = "seed-test-hub") -> Hub:
        if owner is None:
            owner = await seed_user()

        hub = Hub(
            name=name,
            slug=slug,
            description="Integration test hub",
            owner_id=owner.id,
        )
        real_db_session.add(hub)
        await real_db_session.flush()
        await real_db_session.refresh(hub)

        member = HubMember(
            hub_id=hub.id,
            user_id=owner.id,
            role="owner",
        )
        real_db_session.add(member)
        await real_db_session.flush()

        return hub

    return _create_hub


@pytest.fixture
async def seed_workflow(real_db_session, seed_hub) -> Callable:
    """Factory fixture to create test workflows linked to hub."""
    from common.models.workflow import Workflow

    async def _create_workflow(hub=None, name: str = "Seed Test Workflow") -> Workflow:
        if hub is None:
            hub = await seed_hub()

        workflow = Workflow(
            hub_id=hub.id,
            name=name,
            description="Integration test workflow",
            canvas_nodes=[
                {"id": "node-1", "type": "input", "data": {"label": "Start"}},
                {"id": "node-2", "type": "output", "data": {"label": "End"}},
            ],
            canvas_edges=[
                {"id": "edge-1", "source": "node-1", "target": "node-2"},
            ],
            is_active=True,
        )
        real_db_session.add(workflow)
        await real_db_session.flush()
        await real_db_session.refresh(workflow)
        return workflow

    return _create_workflow


# ──────────────────────────────────────────────
# Subprocess Process Fixtures (Gateway & Inference)
# ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def gateway_process():
    """Session-scoped subprocess starting Gateway uvicorn server on port 8100."""
    cmd = [
        sys.executable, "-m", "uvicorn",
        "gateway.main:app",
        "--host", "127.0.0.1",
        "--port", "8100",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for health check
    health_url = "http://127.0.0.1:8100/health"
    start_time = time.time()
    healthy = False
    while time.time() - start_time < 15:
        try:
            resp = httpx.get(health_url, timeout=1.0)
            if resp.status_code == 200:
                healthy = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    if not healthy:
        proc.terminate()
        logger.warning("Gateway process failed to become healthy within 15s; proceed with transport fixture.")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def inference_process():
    """Session-scoped subprocess starting Inference uvicorn server on port 8110."""
    cmd = [
        sys.executable, "-m", "uvicorn",
        "inference.main:app",
        "--host", "127.0.0.1",
        "--port", "8110",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    health_url = "http://127.0.0.1:8110/health"
    start_time = time.time()
    healthy = False
    while time.time() - start_time < 15:
        try:
            resp = httpx.get(health_url, timeout=1.0)
            if resp.status_code == 200:
                healthy = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    if not healthy:
        proc.terminate()
        logger.warning("Inference process failed to become healthy within 15s; proceed with mock/direct calls.")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ──────────────────────────────────────────────
# Structured Test Logging Hook
# ──────────────────────────────────────────────

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture test execution metrics and write structured JSON logs."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        log_entry = {
            "test_name": item.nodeid,
            "outcome": report.outcome,
            "duration": getattr(report, "duration", 0.0),
            "markers": [mark.name for mark in item.iter_markers()],
            "timestamp": datetime.now().isoformat(),
        }
        if report.failed and report.longrepr:
            log_entry["failure_summary"] = str(report.longrepr)

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed writing test structured log: {e}")
