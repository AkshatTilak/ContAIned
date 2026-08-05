"""Audit logging service and decorator (hubs.md §3.5).

Emits immutable AuditLog rows for all mutating actions with payload redaction,
client IP extraction, and size truncation.
"""

import functools
import ipaddress
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional

from common.config.settings import get_settings
from common.models.database import AuditLog
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("common.services.audit")

REDACT_KEY_PATTERN = re.compile(r"credential|password|secret|token|api[_-]?key|authorization", re.I)
DROP_KEYS = {"credentials_encrypted", "password_hash"}
MAX_PAYLOAD_BYTES = 16384  # 16 KB


def redact(payload: Any) -> Any:
    """Recursively replace keys matching REDACT_KEY_PATTERN with '***' and drop DROP_KEYS."""
    if payload is None:
        return None
    if isinstance(payload, Mapping):
        result = {}
        for k, v in payload.items():
            k_str = str(k)
            if k_str in DROP_KEYS:
                continue
            if REDACT_KEY_PATTERN.search(k_str):
                result[k_str] = "***"
            else:
                result[k_str] = redact(v)
        return result
    elif isinstance(payload, (list, tuple)):
        return [redact(item) for item in payload]
    return payload


def client_ip(request: Request) -> Optional[str]:
    """Extract client IP address, checking TRUST_PROXY_HEADERS for X-Forwarded-For."""
    settings = get_settings()
    ip_str: Optional[str] = None

    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            # Take leftmost IP
            ip_str = x_forwarded_for.split(",")[0].strip()

    if not ip_str and request.client:
        ip_str = request.client.host

    if ip_str:
        try:
            ipaddress.ip_address(ip_str)
            return ip_str[:45]
        except ValueError:
            return None
    return None


def _truncate_payload(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if payload is None:
        return None
    try:
        raw_json = json.dumps(payload)
        if len(raw_json.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            return {"_truncated": True}
    except Exception:
        pass
    return payload


async def record_audit(
    session: AsyncSession,
    *,
    action: str,
    resource_type: str,
    hub_id: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    summary: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Append one audit_log row to the active transaction. Never raises into caller."""
    try:
        redacted_before = _truncate_payload(redact(before))
        redacted_after = _truncate_payload(redact(after))
        truncated_summary = summary[:255] if summary else None

        audit = AuditLog(
            id=str(uuid.uuid4()),
            hub_id=hub_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            summary=truncated_summary,
            before_json=redacted_before,
            after_json=redacted_after,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(audit)
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}", exc_info=True)


def audited(
    *,
    action: str,
    resource_type: str,
    resource_id_arg: Optional[str] = None,
    summary: Optional[str] = None,
):
    """FastAPI decorator that records an audit log row upon successful execution."""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            response = await func(*args, **kwargs)

            try:
                # Extract session, request, hub_context from kwargs
                db = kwargs.get("db") or kwargs.get("session")
                request = kwargs.get("request")
                ctx = kwargs.get("ctx")
                user = kwargs.get("user")

                hub_id = getattr(ctx, "hub_id", None) if ctx else None
                actor_id = getattr(ctx, "user_id", None) if ctx else None
                if not actor_id and user:
                    actor_id = user.get("sub") or user.get("id")

                ip_addr = client_ip(request) if request else None
                res_id = kwargs.get(resource_id_arg) if resource_id_arg else None
                after_data = jsonable_encoder(response) if response else None

                if db and isinstance(after_data, dict):
                    await record_audit(
                        db,
                        action=action,
                        resource_type=resource_type,
                        hub_id=hub_id,
                        actor_user_id=actor_id,
                        resource_id=res_id or after_data.get("id"),
                        summary=summary,
                        after=after_data,
                        ip_address=ip_addr,
                    )
            except Exception as e:
                logger.warning(f"Error in @audited decorator execution: {e}")

            return response
        return wrapper
    return decorator
