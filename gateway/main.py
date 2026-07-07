"""Main entry point for the Gateway backend.

Lightweight FastAPI server (CPU-only) that:
1. Dynamically loads project routes from ACTIVE_PROJECTS
2. Dynamically calls project setup hooks on startup/shutdown
3. Proxies model inference to the separate inference server

Run: uvicorn gateway.main:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from common.config.settings import settings
from common.observability.logger import get_logger, RequestIdMiddleware
from gateway.api import router as api_router
from gateway.api.health import router as health_router
from gateway.core.setup import lifespan

logger = get_logger("gateway")

app = FastAPI(
    title=settings.APP_NAME,
    description="API Gateway for the akshat-ai-platform monorepo",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenTelemetry instrumentation
try:
    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry instrumentation initialized")
except Exception as e:
    logger.warning("Could not initialize OpenTelemetry: %s", e)

# Routes
app.include_router(health_router)
app.include_router(api_router)

logger.info("Gateway app created — active projects: %s", settings.ACTIVE_PROJECTS)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "gateway.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_ENV == "development",
    )
