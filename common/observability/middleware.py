"""Observability middleware and exception handlers for FastAPI applications."""

import logging
import uuid
from typing import Callable
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from common.observability.exceptions import ContAInedException, ErrorResponseSchema

logger = logging.getLogger("common.observability.middleware")


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Middleware to assign and propagate a trace correlation ID across HTTP requests."""

    async def dispatch(self, request: Request, call_next: Callable):
        trace_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.trace_id = trace_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = trace_id
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """Register uniform JSON error handlers on a FastAPI application."""

    @app.exception_handler(ContAInedException)
    async def contained_exception_handler(request: Request, exc: ContAInedException):
        trace_id = getattr(request.state, "trace_id", None)
        logger.warning(
            "ContAIned Exception [%s]: %s (trace_id=%s)",
            exc.error_code,
            exc.message,
            trace_id,
        )
        schema = ErrorResponseSchema(
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
            trace_id=trace_id,
        )
        return JSONResponse(status_code=exc.status_code, content=schema.model_dump())

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        trace_id = getattr(request.state, "trace_id", None)
        error_code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        schema = ErrorResponseSchema(
            error_code=error_code,
            message=str(exc.detail),
            details={"status_code": exc.status_code},
            trace_id=trace_id,
        )
        return JSONResponse(status_code=exc.status_code, content=schema.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        trace_id = getattr(request.state, "trace_id", None)
        schema = ErrorResponseSchema(
            error_code="VALIDATION_ERROR",
            message="Input validation failed.",
            details={"errors": exc.errors()},
            trace_id=trace_id,
        )
        return JSONResponse(status_code=400, content=schema.model_dump())

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        trace_id = getattr(request.state, "trace_id", None)
        logger.error("Unhandled Exception: %s (trace_id=%s)", exc, trace_id, exc_info=True)
        schema = ErrorResponseSchema(
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred.",
            details={"error_type": exc.__class__.__name__},
            trace_id=trace_id,
        )
        return JSONResponse(status_code=500, content=schema.model_dump())
