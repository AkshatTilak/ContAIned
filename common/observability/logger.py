"""Structured logging for the platform.

Provides a consistent logger factory used by all backends and projects.
"""

import contextvars
import json
import logging
import sys
import uuid
import re
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from common.config.settings import settings

# Redacts email, phone, API key, SSN
PII_PATTERNS = {
    "EMAIL": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "PHONE": re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "API_KEY": re.compile(r"\b(?:api[-_]?key|sk_live_[a-zA-Z0-9]+|sk_test_[a-zA-Z0-9]+|sk-[a-zA-Z0-9]{20,})\b", re.IGNORECASE),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}

# Redacts connection strings and credentials
DB_URL_PATTERN = re.compile(r"(postgres(?:ql)?(?:\+asyncpg)?://[^:]+:)([^@]+)(@)")
NEO4J_URL_PATTERN = re.compile(r"(bolt://[^:]+:)([^@]+)(@)")
GENERIC_SECRET_PATTERN = re.compile(r"\b(password|passwd|pass|client_secret|client[-_]?secret|secret|private[-_]?key)\b\s*[:=]\s*['\"]?([^'\"\s&,;]+)['\"]?", re.IGNORECASE)


def scrub_sensitive_data(text: str) -> str:
    """Redacts passwords, API keys, emails, phone numbers, and SSNs from text."""
    if not isinstance(text, str):
        return text

    # Redact DB connection string passwords
    text = DB_URL_PATTERN.sub(r"\1[REDACTED_PASSWORD]\3", text)
    text = NEO4J_URL_PATTERN.sub(r"\1[REDACTED_PASSWORD]\3", text)

    # Redact PII patterns
    for pii_type, regex in PII_PATTERNS.items():
        text = regex.sub(f"[REDACTED_{pii_type}]", text)

    # Redact generic secrets parameters (e.g. password=val)
    def redact_secret(match):
        param_name = match.group(1)
        full_match = match.group(0)
        if "=" in full_match:
            return f"{param_name}=[REDACTED]"
        elif ":" in full_match:
            return f"{param_name}: [REDACTED]"
        return f"{param_name}=[REDACTED]"

    text = GENERIC_SECRET_PATTERN.sub(redact_secret, text)
    return text


# Context variable to hold the current request ID
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestIdFormatter(logging.Formatter):
    """Standard formatter that appends the request_id to text logs and redacts sensitive data."""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get() or "-"
        formatted = super().format(record)
        return scrub_sensitive_data(formatted)


class JSONFormatter(logging.Formatter):
    """JSON formatter that formats logging records as JSON objects for production and redacts sensitive data."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": scrub_sensitive_data(record.getMessage()),
            "request_id": request_id_var.get() or "-",
        }
        if record.exc_info:
            log_entry["exception"] = scrub_sensitive_data(self.formatException(record.exc_info))
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
