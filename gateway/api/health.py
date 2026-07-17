"""Health check endpoint for the gateway.

Reports active projects and inference server connectivity.
"""

from fastapi import APIRouter

from common.clients.inference import InferenceClient
from common.config.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """System health check — reports active projects, connection status grid, and inference metrics."""
    # 1. Postgres Database connection check
    db_status = "connected"
    try:
        from common.clients.postgres import get_sessionmaker
        from sqlalchemy import text
        session_factory = get_sessionmaker()
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "unreachable"

    # 2. Redis connection check
    redis_status = "connected"
    try:
        from common.clients.redis import verify_redis_connection
        await verify_redis_connection()
    except Exception:
        redis_status = "unreachable"

    # 3. Neo4j connection check
    neo4j_status = "connected"
    try:
        from common.clients.neo4j import verify_neo4j_connection
        await verify_neo4j_connection()
    except Exception:
        neo4j_status = "unreachable"

    # 4. Qdrant connection check
    qdrant_status = "connected"
    try:
        from common.clients.qdrant import VectorClient
        qdrant_client = VectorClient()
        await qdrant_client.verify_connection()
    except Exception:
        qdrant_status = "unreachable"

    # 5. Kafka connection check
    kafka_status = "connected"
    try:
        import asyncio
        from confluent_kafka.admin import AdminClient
        conf = {"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS, "socket.timeout.ms": 1000}
        admin_client = AdminClient(conf)
        await asyncio.to_thread(admin_client.list_topics, timeout=1.0)
    except Exception:
        kafka_status = "unreachable"

    # 6. Inference Server detailed check
    inference_status = "unknown"
    inference_details = {}
    try:
        client = InferenceClient(base_url=settings.INFERENCE_SERVER_URL)
        health = await client.health()
        inference_status = health.get("status", "connected")
        inference_details = health
        await client.close()
    except Exception:
        inference_status = "unreachable"

    return {
        "status": "healthy",
        "environment": settings.APP_ENV,
        "active_projects": settings.ACTIVE_PROJECTS,
        "services": {
            "gateway": "connected",
            "inference_server": inference_status,
            "database": db_status,
            "redis": redis_status,
            "neo4j": neo4j_status,
            "qdrant": qdrant_status,
            "kafka": kafka_status,
        },
        "inference_details": inference_details,
    }

