"""Main entry point for the Gateway backend.

Lightweight FastAPI server (CPU-only) that:
1. Dynamically loads project routes from ACTIVE_PROJECTS
2. Dynamically calls project setup hooks on startup/shutdown
3. Proxies model inference to the separate inference server

Run: uvicorn gateway.main:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, status, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import json

from common.config.settings import settings
from common.observability.logger import get_logger, RequestIdMiddleware, RequestAuditMiddleware, log_security_event
from common.observability.limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from gateway.api import router as api_router
from gateway.api.health import router as health_router
from gateway.core.setup import lifespan


async def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    client_ip = request.client.host if request.client else "unknown"
    log_security_event(
        "RATE_LIMIT_VIOLATION",
        {
            "client_ip": client_ip,
            "path": request.url.path,
            "method": request.method,
            "limit": str(exc.detail),
        }
    )
    return _rate_limit_exceeded_handler(request, exc)

logger = get_logger("gateway")


class RequestSizeLimitMiddleware:
    """ASGI middleware to enforce request body size limits early in the request cycle."""

    def __init__(self, app, max_upload_size: int, max_json_size: int):
        self.app = app
        self.max_upload_size = max_upload_size
        self.max_json_size = max_json_size

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            content_length = 0
            for header, value in scope.get("headers", []):
                if header.lower() == b"content-length":
                    try:
                        content_length = int(value)
                    except ValueError:
                        pass
                    break

            content_type = b""
            for header, value in scope.get("headers", []):
                if header.lower() == b"content-type":
                    content_type = value.lower()
                    break

            is_multipart = b"multipart/form-data" in content_type
            max_allowed = self.max_upload_size if is_multipart else self.max_json_size

            if content_length > max_allowed:
                await send({
                    "type": "http.response.start",
                    "status": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    "headers": [
                        (b"content-type", b"application/json"),
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": json.dumps({"detail": f"Request body too large. Limit is {max_allowed} bytes."}).encode("utf-8"),
                })
                return

        await self.app(scope, receive, send)


from common.clients.inference import InferenceServerError
from fastapi.responses import JSONResponse


from common.observability.tracing import setup_tracing
setup_tracing("gateway")


from common.observability import register_exception_handlers, TraceIdMiddleware

app = FastAPI(
    title=settings.APP_NAME,
    description="API Gateway for the contained-ai-platform monorepo",
    version=settings.PLATFORM_VERSION,
    lifespan=lifespan,
)

# Limiter settings
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_exceeded_handler)
register_exception_handlers(app)


@app.exception_handler(InferenceServerError)
async def inference_server_error_handler(request: Request, exc: InferenceServerError):
    logger.error("Inference server error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error_code": "EXTERNAL_SERVICE_ERROR",
            "message": f"Inference server is unavailable: {str(exc)}",
            "details": {"service": "inference"},
            "trace_id": getattr(request.state, "trace_id", None),
        },
    )

app.add_middleware(TraceIdMiddleware)

# Middleware
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    RequestSizeLimitMiddleware,
    max_upload_size=settings.MAX_UPLOAD_SIZE,
    max_json_size=settings.MAX_JSON_SIZE,
)
app.add_middleware(RequestAuditMiddleware)
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
        timeout_graceful_shutdown=settings.TIMEOUT_GRACEFUL_SHUTDOWN,
    )
