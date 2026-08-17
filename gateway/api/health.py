"""Health check endpoint for the gateway.

Reports active projects and inference server connectivity.
"""

from fastapi import APIRouter

from common.config.settings import settings

router = APIRouter(tags=["health"])


import asyncio
import time
from fastapi import APIRouter


router = APIRouter(tags=["health"])


import socket


async def _is_port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    loop = asyncio.get_running_loop()
    def check():
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False
    return await loop.run_in_executor(None, check)


async def _check_db():
    start_t = time.perf_counter()
    if not await _is_port_open("127.0.0.1", 5432):
        return "unreachable", -1
    try:
        from common.clients.postgres import get_sessionmaker
        from sqlalchemy import text
        session_factory = get_sessionmaker()
        async with session_factory() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=10.0)
        return "connected", round((time.perf_counter() - start_t) * 1000, 2)
    except Exception:
        return "unreachable", -1


async def _check_redis():
    start_t = time.perf_counter()
    if not await _is_port_open("127.0.0.1", 6379):
        return "unreachable", -1
    try:
        from common.clients.redis import verify_redis_connection
        await asyncio.wait_for(verify_redis_connection(), timeout=10.0)
        return "connected", round((time.perf_counter() - start_t) * 1000, 2)
    except Exception:
        return "unreachable", -1


async def _check_neo4j():
    start_t = time.perf_counter()
    if not await _is_port_open("127.0.0.1", 7687):
        return "unreachable", -1
    try:
        from common.clients.neo4j import verify_neo4j_connection
        await asyncio.wait_for(verify_neo4j_connection(), timeout=10.0)
        return "connected", round((time.perf_counter() - start_t) * 1000, 2)
    except Exception:
        return "unreachable", -1


async def _check_qdrant():
    start_t = time.perf_counter()
    if not await _is_port_open("127.0.0.1", 6333):
        return "unreachable", -1
    try:
        from common.clients.qdrant import VectorClient
        qdrant_client = VectorClient()
        await asyncio.wait_for(qdrant_client.verify_connection(max_retries=1), timeout=10.0)
        return "connected", round((time.perf_counter() - start_t) * 1000, 2)
    except Exception:
        return "unreachable", -1


async def _check_kafka():
    start_t = time.perf_counter()
    if not await _is_port_open("127.0.0.1", 9092):
        return "unreachable", -1
    return "connected", round((time.perf_counter() - start_t) * 1000, 2)


async def _check_inference():
    start_t = time.perf_counter()
    if not await _is_port_open("127.0.0.1", 8010):
        return "unreachable", -1, {}
    try:
        import httpx
        url = f"{settings.INFERENCE_SERVER_URL.rstrip('/')}/health"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                health = resp.json()
                status_val = health.get("status", "connected")
                return status_val, round((time.perf_counter() - start_t) * 1000, 2), health
        return "unreachable", -1, {}
    except Exception:
        return "unreachable", -1, {}


from fastapi import APIRouter, Response, status


@router.get("/health")
@router.get("/api/health")
async def health_check(response: Response) -> dict:
    """System health check — reports active projects, connection status grid, and inference metrics concurrently."""
    results = await asyncio.gather(
        _check_db(),
        _check_redis(),
        _check_neo4j(),
        _check_qdrant(),
        _check_kafka(),
        _check_inference(),
        return_exceptions=True,
    )

    db_res = results[0] if isinstance(results[0], tuple) else ("unreachable", -1)
    redis_res = results[1] if isinstance(results[1], tuple) else ("unreachable", -1)
    neo4j_res = results[2] if isinstance(results[2], tuple) else ("unreachable", -1)
    qdrant_res = results[3] if isinstance(results[3], tuple) else ("unreachable", -1)
    kafka_res = results[4] if isinstance(results[4], tuple) else ("unreachable", -1)
    inf_res = results[5] if isinstance(results[5], tuple) else ("unreachable", -1, {})

    db_status, db_lat = db_res
    redis_status, redis_lat = redis_res
    neo4j_status, neo4j_lat = neo4j_res
    qdrant_status, qdrant_lat = qdrant_res
    kafka_status, kafka_lat = kafka_res
    inf_status, inf_lat, inf_details = inf_res

    latencies = {
        "database": db_lat,
        "redis": redis_lat,
        "neo4j": neo4j_lat,
        "qdrant": qdrant_lat,
        "kafka": kafka_lat,
        "inference_server": inf_lat,
    }

    # Core services: database, redis, qdrant
    core_healthy = all(s == "connected" for s in [db_status, redis_status, qdrant_status])
    # Non-critical services: neo4j, kafka, inference_server
    non_critical_healthy = all(s == "connected" for s in [neo4j_status, kafka_status, inf_status])

    if core_healthy:
        overall_status = "healthy" if non_critical_healthy else "degraded"
        response.status_code = status.HTTP_200_OK
    else:
        overall_status = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": overall_status,
        "platform_version": getattr(settings, "PLATFORM_VERSION", "3.0.0"),
        "environment": settings.APP_ENV,
        "auth_enabled": getattr(settings, "AUTH_ENABLED", False),
        "active_projects": settings.ACTIVE_PROJECTS,
        "services": {
            "gateway": "connected",
            "inference_server": inf_status,
            "database": db_status,
            "redis": redis_status,
            "neo4j": neo4j_status,
            "qdrant": qdrant_status,
            "kafka": kafka_status,
        },
        "latencies_ms": latencies,
        "inference_details": inf_details,
    }

