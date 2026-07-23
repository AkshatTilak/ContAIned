"""API Key Authentication & Rate Limiting Middleware for `/v1/*` routes.

Validates OpenAI-compatible API keys, enforces per-key Redis rate limiting,
attaches rate limit headers, and tracks request metadata.
"""

import time
import json
import logging
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from sqlalchemy import select

from common.clients.postgres import get_sessionmaker
from common.clients.redis import get_redis_client
from common.models.database import APIKeyModel, APIKeyUsageModel
from gateway.api.api_keys import hash_api_key

logger = logging.getLogger("gateway.auth.api_key_middleware")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware for validating API keys and rate limits on `/v1/*` routes."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only apply to /v1/* endpoints
        path = request.url.path
        if not path.startswith("/v1"):
            return await call_next(request)

        # 1. Extract Bearer token
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Missing or invalid Authorization header. Expected 'Authorization: Bearer sk-...'",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            )

        raw_key = auth_header.replace("Bearer ", "").strip()
        if not raw_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "API key is empty.",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            )

        hashed_key = hash_api_key(raw_key)

        # 2. Look up key in DB
        api_key_id = None
        rate_limit = 60
        user_id = None

        session_factory = get_sessionmaker()
        async with session_factory() as db:
            stmt = select(APIKeyModel).where(APIKeyModel.key == hashed_key)
            res = await db.execute(stmt)
            api_key_obj = res.scalar_one_or_none()
            if api_key_obj and api_key_obj.is_active:
                api_key_id = api_key_obj.id
                rate_limit = api_key_obj.rate_limit or 60
                user_id = api_key_obj.user_id
                api_key_obj.usage_count = (api_key_obj.usage_count or 0) + 1
                await db.commit()

        if not api_key_id:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Invalid or inactive API key.",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            )

        # 3. Redis Rate Limiting (sliding window per minute)
        current_time = int(time.time())
        minute_bucket = current_time // 60
        reset_seconds = 60 - (current_time % 60)
        redis_key = f"ratelimit:apikey:{api_key_id}:{minute_bucket}"

        current_requests = 1
        remaining_requests = rate_limit - 1

        redis = get_redis_client()
        if redis:
            try:
                pipe = redis.pipeline()
                pipe.incr(redis_key)
                pipe.expire(redis_key, 90)
                results = await pipe.execute()
                current_requests = results[0]
                remaining_requests = max(0, rate_limit - current_requests)
            except Exception as e:
                logger.warning("Redis rate limit check failed, degrading gracefully: %s", e)

        if current_requests > rate_limit:
            return JSONResponse(
                status_code=429,
                headers={
                    "Retry-After": str(reset_seconds),
                    "X-RateLimit-Limit": str(rate_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_seconds),
                },
                content={
                    "error": {
                        "message": f"Rate limit exceeded. Maximum allowed: {rate_limit} requests/minute.",
                        "type": "requests",
                        "param": None,
                        "code": "rate_limit_exceeded",
                    }
                },
            )

        # Store context in request state
        request.state.api_key_id = api_key_id
        request.state.user_id = user_id

        # 4. Proceed with request and time execution
        start_time = time.time()
        response = await call_next(request)
        latency_ms = (time.time() - start_time) * 1000

        # Inject rate limit headers
        response.headers["X-RateLimit-Limit"] = str(rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining_requests)
        response.headers["X-RateLimit-Reset"] = str(reset_seconds)

        # 5. Log usage to DB
        try:
            model_used = getattr(request.state, "model_used", None)
            input_tokens = getattr(request.state, "input_tokens", 0)
            output_tokens = getattr(request.state, "output_tokens", 0)

            async with session_factory() as db:
                usage = APIKeyUsageModel(
                    api_key_id=api_key_id,
                    endpoint=path,
                    model_used=model_used,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=round(latency_ms, 2),
                    status_code=response.status_code,
                )
                db.add(usage)
                await db.commit()
        except Exception as e:
            logger.warning("Failed to log API key usage: %s", e)

        return response
