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

from sqlalchemy import event

logger = logging.getLogger("tests.conftest")

# Log Directory setup
LOG_DIR = ROOT_DIR / "tests" / "logs" / datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "test_run.jsonl"

# Thread/Task test diagnostic storage
current_test_diagnostics = {
    "nodeid": None,
    "trace_id": None,
    "db_queries": [],
    "http_requests": [],
}
_session_test_results = []


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

def _before_cursor_execute(conn, cursor, statement, parameters, context, execmany):
    conn.info.setdefault("query_start_time", []).append(time.perf_counter())


def _after_cursor_execute(conn, cursor, statement, parameters, context, execmany):
    start_times = conn.info.get("query_start_time", [])
    if start_times:
        start_time = start_times.pop()
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        stmt_short = statement.strip()[:200]
        current_test_diagnostics["db_queries"].append({
            "statement": stmt_short,
            "duration_ms": round(duration_ms, 2),
        })


import uuid


@pytest.fixture(autouse=True)
def setup_test_diagnostics(request):
    """Reset diagnostics and generate X-Test-Trace-ID per test."""
    trace_id = f"test-{uuid.uuid4().hex[:12]}"
    current_test_diagnostics["nodeid"] = request.node.nodeid
    current_test_diagnostics["trace_id"] = trace_id
    current_test_diagnostics["db_queries"] = []
    current_test_diagnostics["http_requests"] = []
    yield


from sqlalchemy.pool import NullPool


@pytest.fixture(scope="session")
def test_engine():
    """Session-scoped SQLAlchemy engine connecting to test database."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
    )
    event.listen(engine.sync_engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(engine.sync_engine, "after_cursor_execute", _after_cursor_execute)
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


class TracingASGITransport(httpx.ASGITransport):
    """Custom ASGI Transport that injects X-Test-Trace-ID header and logs HTTP metrics."""
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        trace_id = current_test_diagnostics.get("trace_id") or "no-trace-id"
        request.headers["X-Test-Trace-ID"] = trace_id
        start_time = time.perf_counter()
        response = await super().handle_async_request(request)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Safely measure request body size. Multipart/streaming bodies raise
        # httpx.RequestNotRead when accessed via `request.content`; read them first.
        try:
            req_bytes = len(request.content) if request.content else 0
        except httpx.RequestNotRead:
            try:
                await request.aread()
                req_bytes = len(request.content)
            except Exception:
                req_bytes = 0
        content_bytes = getattr(response, "_content", None)
        resp_bytes = len(content_bytes) if content_bytes is not None else int(response.headers.get("content-length", 0))

        current_test_diagnostics["http_requests"].append({
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "req_bytes": req_bytes,
            "resp_bytes": resp_bytes,
            "trace_id": trace_id,
        })
        return response


@pytest.fixture
async def gateway_client(real_db_session) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client fixture with database dependency override against Gateway ASGI app."""
    async def override_get_db():
        yield real_db_session

    gateway_app.dependency_overrides[get_async_db] = override_get_db
    transport = TracingASGITransport(app=gateway_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    gateway_app.dependency_overrides.clear()



# ──────────────────────────────────────────────
# Factory Fixture Chain (User -> Hub -> Workflow)
# ──────────────────────────────────────────────

@pytest.fixture
async def seed_user(real_db_session) -> Callable:
    """Factory fixture to create test users in DB."""
    from common.models.database import User
    from gateway.auth.passwords import hash_password

    async def _create_user(
        email: str = None,
        display_name: str = "Seed Test User",
        role: str = "admin",
        password: str = "TestPass123!"
    ) -> User:
        if email is None:
            email = f"test_user_{uuid.uuid4().hex[:8]}@contained.ai"
        user = User(
            email=email,
            display_name=display_name,
            platform_role=role,
            password_hash=hash_password(password),
            status="active",
        )
        real_db_session.add(user)
        await real_db_session.flush()
        await real_db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
async def seed_hub(real_db_session, seed_user) -> Callable:
    """Factory fixture to create test hubs linked to user."""
    from common.models.database import Hub, HubMember

    async def _create_hub(owner=None, name: str = "Seed Test Hub", slug: str = None, hub_type: str = "agent") -> Hub:
        if owner is None:
            owner = await seed_user()
        if slug is None:
            slug = f"seed-hub-{uuid.uuid4().hex[:8]}"

        hub = Hub(
            name=name,
            slug=slug,
            hub_type=hub_type,
            description="Integration test hub",
            owner_id=owner.id,
        )
        real_db_session.add(hub)
        await real_db_session.flush()
        await real_db_session.refresh(hub)

        member = HubMember(
            hub_id=hub.id,
            user_id=owner.id,
            hub_role="owner",
        )
        real_db_session.add(member)
        await real_db_session.flush()

        return hub

    return _create_hub



@pytest.fixture
async def seed_workflow(real_db_session, seed_hub) -> Callable:
    """Factory fixture to create test workflows linked to hub."""
    from common.models.database import Workflow


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
    """Session-scoped process fixture connecting to or starting Gateway uvicorn server on port 8000."""
    port = getattr(settings, "APP_PORT", 8000)
    health_url = f"http://127.0.0.1:{port}/health"
    
    # Check if Gateway service is already running
    try:
        resp = httpx.get(health_url, timeout=1.0)
        if resp.status_code == 200:
            logger.info(f"Gateway is already running on port {port}. Reusing running service.")
            yield None
            return
    except Exception:
        pass

    cmd = [
        sys.executable, "-m", "uvicorn",
        "gateway.main:app",
        "--host", "127.0.0.1",
        "--port", str(port),
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for health check
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
        logger.warning(f"Gateway process failed to become healthy on port {port} within 15s; proceed with transport fixture.")

    yield proc

    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def inference_process():
    """Session-scoped process fixture connecting to or starting Inference uvicorn server on port 8010."""
    port = getattr(settings, "INFERENCE_SERVER_PORT", 8010)
    health_url = f"http://127.0.0.1:{port}/health"

    # Check if Inference service is already running
    try:
        resp = httpx.get(health_url, timeout=1.0)
        if resp.status_code == 200:
            logger.info(f"Inference server is already running on port {port}. Reusing running service.")
            yield None
            return
    except Exception:
        pass

    cmd = [
        sys.executable, "-m", "uvicorn",
        "inference.main:app",
        "--host", "127.0.0.1",
        "--port", str(port),
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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
        logger.warning(f"Inference process failed to become healthy on port {port} within 15s; proceed with mock/direct calls.")

    yield proc

    if proc and proc.poll() is None:
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
    """Capture test execution metrics, failure diagnostics, and write structured JSON logs."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        log_entry = {
            "test_name": item.nodeid,
            "outcome": report.outcome,
            "duration": getattr(report, "duration", 0.0),
            "markers": [mark.name for mark in item.iter_markers()],
            "timestamp": datetime.now().isoformat(),
            "trace_id": current_test_diagnostics.get("trace_id"),
            "db_query_count": len(current_test_diagnostics.get("db_queries", [])),
            "db_total_duration_ms": round(sum(q["duration_ms"] for q in current_test_diagnostics.get("db_queries", [])), 2),
            "http_request_count": len(current_test_diagnostics.get("http_requests", [])),
        }
        if report.failed:
            if report.longrepr:
                log_entry["failure_summary"] = str(report.longrepr)
            log_entry["diagnostics"] = {
                "recent_http_requests": current_test_diagnostics.get("http_requests", [])[-10:],
                "recent_db_queries": current_test_diagnostics.get("db_queries", [])[-10:],
            }

        _session_test_results.append(log_entry)

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed writing test structured log: {e}")


def pytest_sessionfinish(session, exitstatus):
    """Generate session summary report at end of test run."""
    total = len(_session_test_results)
    if total == 0:
        return

    passed = sum(1 for r in _session_test_results if r["outcome"] == "passed")
    failed = sum(1 for r in _session_test_results if r["outcome"] == "failed")
    skipped = sum(1 for r in _session_test_results if r["outcome"] == "skipped")

    slowest = sorted(_session_test_results, key=lambda x: x["duration"], reverse=True)[:5]
    db_heavy = sorted(_session_test_results, key=lambda x: x["db_query_count"], reverse=True)[:5]

    summary = {
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "slowest_tests": [{"name": t["test_name"], "duration": t["duration"]} for t in slowest],
        "most_db_heavy_tests": [{"name": t["test_name"], "db_queries": t["db_query_count"]} for t in db_heavy],
        "finished_at": datetime.now().isoformat(),
    }

    summary_file = LOG_DIR / "summary.json"
    try:
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except Exception as e:
        logger.error(f"Failed writing summary log: {e}")

    print("\n" + "=" * 60)
    print("               TEST RUN OBSERVABILITY SUMMARY               ")
    print("=" * 60)
    print(f"Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    print("-" * 60)
    print("Top Slowest Tests:")
    for t in slowest[:3]:
        print(f"  - {t['test_name']}: {t['duration']:.2f}s")
    print("-" * 60)
    print("Top DB-Heavy Tests:")
    for t in db_heavy[:3]:
        print(f"  - {t['test_name']}: {t['db_query_count']} queries ({t['db_total_duration_ms']}ms)")
    print("=" * 60 + "\n")

