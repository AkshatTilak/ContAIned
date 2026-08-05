"""Structured logging for the platform.

Provides a consistent logger factory and file logging configuration used by
all backends and projects.  Call `configure_file_logging(service_name)` once
at process startup (e.g. in main.py) to activate rotating file output.
"""

import contextvars
import json
import logging
import logging.handlers
import sys
import uuid
import re
import time
import traceback
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from common.config.settings import settings

# ---------------------------------------------------------------------------
# PII / secret scrubbing
# ---------------------------------------------------------------------------

PII_PATTERNS = {
    "EMAIL": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "PHONE": re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "API_KEY": re.compile(r"\b(?:api[-_]?key|sk_live_[a-zA-Z0-9]+|sk_test_[a-zA-Z0-9]+|sk-[a-zA-Z0-9]{20,})\b", re.IGNORECASE),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}

DB_URL_PATTERN = re.compile(r"(postgres(?:ql)?(?:\+asyncpg)?://[^:]+:)([^@]+)(@)")
NEO4J_URL_PATTERN = re.compile(r"(bolt://[^:]+:)([^@]+)(@)")
GENERIC_SECRET_PATTERN = re.compile(
    r"\b(password|passwd|pass|client_secret|client[-_]?secret|secret|private[-_]?key)\b\s*[:=]\s*['\"]?([^'\"\s&,;]+)['\"]?",
    re.IGNORECASE,
)


def scrub_sensitive_data(text: str) -> str:
    """Redacts passwords, API keys, emails, phone numbers, and SSNs from text."""
    if not isinstance(text, str):
        return text
    text = DB_URL_PATTERN.sub(r"\1[REDACTED_PASSWORD]\3", text)
    text = NEO4J_URL_PATTERN.sub(r"\1[REDACTED_PASSWORD]\3", text)
    for pii_type, regex in PII_PATTERNS.items():
        text = regex.sub(f"[REDACTED_{pii_type}]", text)

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


# ---------------------------------------------------------------------------
# Context / formatters
# ---------------------------------------------------------------------------

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestIdFormatter(logging.Formatter):
    """Text formatter that injects request_id and scrubs PII."""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get() or "-"
        formatted = super().format(record)
        return scrub_sensitive_data(formatted)


class JSONFormatter(logging.Formatter):
    """JSON formatter for production; scrubs PII and includes exc info."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": scrub_sensitive_data(record.getMessage()),
            "request_id": request_id_var.get() or "-",
        }
        if record.exc_info:
            log_entry["exception"] = scrub_sensitive_data(self.formatException(record.exc_info))
        return json.dumps(log_entry)


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

_CONSOLE_TEXT_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(request_id)s | %(message)s"
_CONSOLE_DATE_FMT = "%Y-%m-%d %H:%M:%S"
_FILE_TEXT_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(request_id)s | %(message)s"


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Return a structured logger with a console handler.

    Call `configure_file_logging()` once at startup to also add file handlers.
    """
    logger = logging.getLogger(name)
    logger.propagate = True

    if level is None:
        level = settings.LOG_LEVEL

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if settings.APP_ENV == "production":
            formatter: logging.Formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%SZ")
        else:
            formatter = RequestIdFormatter(fmt=_CONSOLE_TEXT_FMT, datefmt=_CONSOLE_DATE_FMT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


# ---------------------------------------------------------------------------
# File logging — call once at process startup
# ---------------------------------------------------------------------------

_file_logging_configured = False


def configure_file_logging(service_name: str, log_dir: Optional[str] = None) -> None:
    """Attach rotating file handlers to the root logger.

    Creates:
      <log_dir>/<service_name>.log   — all messages at LOG_LEVEL and above
      <log_dir>/errors.log           — ERROR and CRITICAL only (all services)

    Rotation: 10 MB per file, keep 5 backups.
    Safe to call multiple times (idempotent after first call).

    Args:
        service_name: e.g. 'gateway' or 'inference'.
        log_dir: directory for log files; defaults to <repo_root>/logs.
    """
    global _file_logging_configured
    if _file_logging_configured:
        return

    resolved_dir = Path(log_dir) if log_dir else Path(__file__).parents[2] / "logs"
    resolved_dir.mkdir(parents=True, exist_ok=True)

    level_str = settings.LOG_LEVEL.upper()
    log_level = getattr(logging, level_str, logging.INFO)

    if settings.APP_ENV == "production":
        fmt: logging.Formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%SZ")
    else:
        fmt = RequestIdFormatter(fmt=_FILE_TEXT_FMT, datefmt=_CONSOLE_DATE_FMT)

    # --- per-service rotating handler ---
    service_log = resolved_dir / f"{service_name}.log"
    service_handler = logging.handlers.RotatingFileHandler(
        service_log,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    service_handler.setLevel(log_level)
    service_handler.setFormatter(fmt)

    # --- shared errors-only handler ---
    errors_log = resolved_dir / "errors.log"
    errors_handler = logging.handlers.RotatingFileHandler(
        errors_log,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    errors_handler.setLevel(logging.ERROR)
    errors_handler.setFormatter(fmt)

    # Attach to root logger so every child logger writes to files automatically
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # root must pass everything; handlers filter
    for h in (service_handler, errors_handler):
        root.addHandler(h)

    _file_logging_configured = True
    logging.getLogger("common.observability.logger").info(
        "File logging active → %s | errors → %s",
        service_log,
        errors_log,
    )


# ---------------------------------------------------------------------------
# Request middleware
# ---------------------------------------------------------------------------

class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate/propagate X-Request-ID and update the logging context."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)


platform_logger = get_logger("platform")


class RequestAuditMiddleware(BaseHTTPMiddleware):
    """Audit all incoming HTTP requests — logs metadata, latency, and on 5xx
    the full exception traceback so errors are always traceable.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        log_bodies = getattr(settings, "LOG_BODIES", False)
        is_dev = settings.APP_ENV == "development"

        body_preview: Optional[str] = None
        if is_dev and log_bodies:
            try:
                body_bytes = await request.body()
                body_preview = scrub_sensitive_data(body_bytes.decode("utf-8", errors="ignore"))[:500]

                async def receive():
                    return {"type": "http.request", "body": body_bytes, "more_body": False}

                request._receive = receive  # type: ignore[attr-defined]
            except Exception:
                body_preview = "[error reading body]"

        response = None
        exc_to_log: Optional[BaseException] = None
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            exc_to_log = exc
            raise
        finally:
            process_time = (time.time() - start_time) * 1000.0
            status_code = response.status_code if response else 500
            client_host = request.client.host if request.client else "unknown"
            trace_id = getattr(request.state, "trace_id", "-")

            base_msg = (
                f"{request.method} {request.url.path} "
                f"from {client_host} -> {status_code} "
                f"(Latency: {process_time:.2f}ms | trace={trace_id})"
            )
            if body_preview:
                base_msg += f" | body={body_preview}"

            audit_logger = get_logger("audit")
            if status_code >= 500 or exc_to_log is not None:
                # Include full traceback so errors.log has everything needed to diagnose
                if exc_to_log is not None:
                    tb = traceback.format_exception(type(exc_to_log), exc_to_log, exc_to_log.__traceback__)
                    base_msg += "\n" + "".join(tb)
                audit_logger.error(base_msg)
            elif status_code >= 400:
                audit_logger.warning(base_msg)
            else:
                audit_logger.info(base_msg)


# ---------------------------------------------------------------------------
# Security event helper
# ---------------------------------------------------------------------------

def log_security_event(event_type: str, details: Dict[str, Any]) -> None:
    """Log a security or compliance event with structured details."""
    sec_logger = get_logger("security")
    scrubbed = {k: scrub_sensitive_data(v) if isinstance(v, str) else v for k, v in details.items()}
    sec_logger.warning("SECURITY_EVENT | Type: %s | Details: %s", event_type, json.dumps(scrubbed))
