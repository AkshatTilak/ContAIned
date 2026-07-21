"""Health check endpoint for the gateway.

Reports active projects and inference server connectivity.
"""

from fastapi import APIRouter

from common.clients.inference import InferenceClient
from common.config.settings import settings

router = APIRouter(tags=["health"])


import asyncio
import time
from fastapi import APIRouter

from common.clients.inference import InferenceClient
from common.config.settings import settings

router = APIRouter(tags=["health"])


async def _check_db():
    start_t = time.perf_counter()
    try:
        from common.clients.postgres import get_sessionmaker
        from sqlalchemy import text
        session_factory = get_sessionmaker()
        async with session_factory() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=1.0)
        return "connected", round((time.perf_counter() - start_t) * 1000, 2)
    except Exception:
        return "unreachable", -1


async def _check_redis():
    start_t = time.perf_counter()
    try:
        from common.clients.redis import verify_redis_connection
        await asyncio.wait_for(verify_redis_connection(), timeout=1.0)
        return "connected", round((time.perf_counter() - start_t) * 1000, 2)
    except Exception:
        return "unreachable", -1


async def _check_neo4j():
    start_t = time.perf_counter()
    try:
        from common.clients.neo4j import verify_neo4j_connection
        await asyncio.wait_for(verify_neo4j_connection(), timeout=1.0)
        return "connected", round((time.perf_counter() - start_t) * 1000, 2)
    except Exception:
        return "unreachable", -1


async def _check_qdrant():
    start_t = time.perf_counter()
    try:
        from common.clients.qdrant import VectorClient
        qdrant_client = VectorClient()
        await asyncio.wait_for(qdrant_client.verify_connection(), timeout=1.0)
        return "connected", round((time.perf_counter() - start_t) * 1000, 2)
    except Exception:
        return "unreachable", -1


async def _check_kafka():
    start_t = time.perf_counter()
    try:
        from confluent_kafka.admin import AdminClient
        conf = {"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS, "socket.timeout.ms": 1000}
        admin_client = AdminClient(conf)
        await asyncio.wait_for(asyncio.to_thread(admin_client.list_topics, timeout=1.0), timeout=1.0)
        return "connected", round((time.perf_counter() - start_t) * 1000, 2)
    except Exception:
        return "unreachable", -1


async def _check_inference():
    start_t = time.perf_counter()
    try:
        client = InferenceClient(base_url=settings.INFERENCE_SERVER_URL)
        health = await asyncio.wait_for(client.health(), timeout=1.0)
        status_val = health.get("status", "connected")
        await client.close()
        return status_val, round((time.perf_counter() - start_t) * 1000, 2), health
    except Exception:
        return "unreachable", -1, {}


@router.get("/health")
async def health_check() -> dict:
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

    return {
        "status": "healthy",
        "platform_version": getattr(settings, "PLATFORM_VERSION", "3.0.0"),
        "environment": settings.APP_ENV,
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

