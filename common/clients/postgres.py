"""Database client wrapper for PostgreSQL using SQLAlchemy.

Supports robust connection pooling and handles session lifecycle.
Shared across all projects and backends.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.config.settings import settings

logger = logging.getLogger("common.database")

_engine = None
_SessionLocal = None


def get_engine():
    """Get or initialize the SQLAlchemy database engine."""
    global _engine
    if _engine is None:
        try:
            _engine = create_async_engine(
                settings.DATABASE_URL,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
            )
        except SQLAlchemyError as e:
            logger.error("Failed to initialize database engine: %s", e)
            raise ConnectionError("Database initialization failed") from e
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Get or initialize the session maker."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _SessionLocal


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency generator to retrieve an async database session.

    Yields:
        An active SQLAlchemy AsyncSession.
    """
    SessionLocal = get_sessionmaker()
    async with SessionLocal() as db:
        try:
            yield db
        except SQLAlchemyError as e:
            logger.error("Database session transaction error: %s", e)
            await db.rollback()
            raise RuntimeError("Database transaction failed") from e


async def verify_connection_with_retry(max_retries: int = 5, backoff_factor: float = 2.0):
    """Verify database connection with exponential backoff on startup."""
    engine = get_engine()
    retries = 0
    delay = 1.0
    while retries < max_retries:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection verified successfully.")
            return
        except Exception as e:
            retries += 1
            if retries >= max_retries:
                logger.error("Failed to connect to database after %d attempts: %s", max_retries, e)
                raise ConnectionError("Database is unreachable") from e
            logger.warning(
                "Database connection attempt %d failed. Retrying in %.2f seconds... Error: %s",
                retries, delay, e
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor


async def close_postgres() -> None:
    """Close the global database engine connection."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine connection closed.")

