"""
Database configuration and session management

No auto-commit - explicit transaction management required.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Naming convention for constraints
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,
)

# Create session factory
# Note: No auto-commit - transactions must be explicitly committed
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database sessions.
    
    IMPORTANT: This dependency does NOT auto-commit.
    You must explicitly call `await session.commit()` to persist changes.
    
    On exception, the session is automatically rolled back.

    Yields:
        AsyncSession: Database session
        
    Example:
        async def create_user(db: AsyncSession, user_data: dict):
            user = User(**user_data)
            db.add(user)
            await db.commit()  # Explicit commit required
            await db.refresh(user)
            return user
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # No auto-commit - caller must explicitly commit
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for getting async database sessions.
    
    IMPORTANT: This context manager does NOT auto-commit.
    You must explicitly call `await session.commit()` to persist changes.
    
    On exception, the session is automatically rolled back.

    Yields:
        AsyncSession: Database session
        
    Example:
        async with get_db_context() as db:
            user = User(**user_data)
            db.add(user)
            await db.commit()  # Explicit commit required
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # No auto-commit - caller must explicitly commit
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def transaction_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database transactions with auto-commit on success.
    
    Use this when you want automatic commit on successful completion.
    On exception, the transaction is rolled back.
    
    Yields:
        AsyncSession: Database session
        
    Example:
        async with transaction_context() as db:
            user = User(**user_data)
            db.add(user)
            # Auto-commits on exit if no exception
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
