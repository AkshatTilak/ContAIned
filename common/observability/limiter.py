"""Shared rate limiting configuration.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from common.config.settings import settings

# Shared Limiter instance using Redis as storage
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=["100/minute"]
)
