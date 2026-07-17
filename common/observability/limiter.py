"""Shared rate limiting configuration.
"""

import logging
import redis
from slowapi import Limiter
from slowapi.util import get_remote_address
from common.config.settings import settings

logger = logging.getLogger("common.limiter")

storage_uri = settings.REDIS_URL
try:
    # Synchronously check Redis connection on startup with a brief timeout
    # to degrade gracefully if Redis is offline
    client = redis.from_url(settings.REDIS_URL, socket_timeout=1.0)
    client.ping()
    logger.info("Limiter initialized with Redis storage: %s", settings.REDIS_URL)
except Exception as e:
    logger.warning(
        "Redis is offline or unreachable for limiter. Falling back to memory storage. Error: %s", e
    )
    storage_uri = "memory://"

# Shared Limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=storage_uri,
    default_limits=["100/minute"]
)
