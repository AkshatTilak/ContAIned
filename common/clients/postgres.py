"""Database client wrapper for PostgreSQL using SQLAlchemy.

Supports robust connection pooling and handles session lifecycle.
Shared across all projects and backends.
"""

import logging
from collections.abc import Generator
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from common.config.settings import settings

logger = logging.getLogger("common.database")

_engine = None
_SessionLocal = None


def get_engine():
    """Get or initialize the SQLAlchemy database engine."""
    global _engine
    if _engine is None:
        try:
            _engine = create_engine(
                settings.DATABASE_URL,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
            )
        except SQLAlchemyError as e:
            logger.error("Failed to initialize database engine: %s", e)
            raise ConnectionError("Database initialization failed") from e
    return _engine


def get_sessionmaker() -> sessionmaker:
    """Get or initialize the session maker."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency generator to retrieve a database session.

    Yields:
        An active SQLAlchemy Session.
    """
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error("Database session transaction error: %s", e)
        db.rollback()
        raise RuntimeError("Database transaction failed") from e
    finally:
        db.close()
