"""Health check endpoint for the gateway.

Reports active projects and inference server connectivity.
"""

from fastapi import APIRouter

from common.clients.inference import InferenceClient
from common.config.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """System health check — reports active projects and backend connectivity."""
    inference_status = "unknown"
    try:
        client = InferenceClient(base_url=settings.INFERENCE_SERVER_URL)
        health = await client.health()
        inference_status = health.get("status", "connected")
        await client.close()
    except Exception:
        inference_status = "unreachable"

    return {
        "status": "healthy",
        "environment": settings.APP_ENV,
        "active_projects": settings.ACTIVE_PROJECTS,
        "inference_server": inference_status,
        "database": "configured" if settings.DATABASE_URL else "missing",
        "qdrant": "configured" if settings.QDRANT_URL else "missing",
    }
