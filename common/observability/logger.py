"""Structured logging for the platform.

Provides a consistent logger factory used by all backends and projects.
"""

import logging
import sys


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Create a structured logger with consistent formatting.

    Args:
        name: Logger name (typically the project/backend name).
        level: Log level string (DEBUG, INFO, WARNING, ERROR).

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


# Pre-configured platform logger
platform_logger = get_logger("platform")
