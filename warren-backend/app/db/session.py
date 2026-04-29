"""Async SQLAlchemy engine, session factory, and declarative base.

Usage:
    from app.db.session import Base, get_db

    # In FastAPI route:
    async def my_route(db: AsyncSession = Depends(get_db)):
        ...

    # In model definitions:
    from app.db.session import Base
    class MyModel(Base):
        ...
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import settings

# Declarative base for all ORM models
Base = declarative_base()

# Build async engine — uses asyncpg for PostgreSQL, aiosqlite for SQLite (tests)
_database_url = (
    settings.DATABASE_URL if settings is not None else "sqlite+aiosqlite:///:memory:"
)


# Convert sync psycopg2/postgresql URLs to async equivalents if needed
def _make_async_url(url: str) -> str:
    """Convert a sync database URL to its async driver equivalent.

    Args:
        url: Database URL string (may be sync or async).

    Returns:
        Async-compatible database URL string.
    """
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
            "postgres://", "postgresql+asyncpg://", 1
        )
    if url.startswith("sqlite://") and "aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


engine = create_async_engine(
    _make_async_url(_database_url),
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Async generator yielding a database session for FastAPI Depends.

    Yields:
        AsyncSession: An open async SQLAlchemy session.

    Example:
        async def route(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Company))
    """
    async with AsyncSessionLocal() as session:
        yield session
