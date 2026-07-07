"""Structured logging for the platform.

Provides a consistent logger factory used by all backends and projects.
"""

import contextvars
import json
import logging
import sys
import uuid
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from common.config.settings import settings

# Context variable to hold the current request ID
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestIdFormatter(logging.Formatter):
    """Standard formatter that appends the request_id to text logs."""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get() or "-"
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter that formats logging records as JSON objects for production."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get() or "-",
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Create a structured logger with consistent formatting.

    Args:
        name: Logger name (typically the project/backend name).
        level: Log level string (DEBUG, INFO, WARNING, ERROR).

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    # Disable propagation to prevent double logging in root logger handlers if present
    logger.propagate = False

    if level is None:
        level = settings.LOG_LEVEL

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if settings.APP_ENV == "production":
            formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%SZ")
        else:
            formatter = RequestIdFormatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(request_id)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


class RequestIdMiddleware(BaseHTTPMiddleware):
    """FastAPI Middleware to generate/propagate X-Request-ID and update the logging context."""

    async def dispatch(self, request: Request, call_next):
        # Extract existing Request ID or generate a new one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)


# Pre-configured platform logger
platform_logger = get_logger("platform")
