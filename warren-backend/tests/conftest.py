"""Shared pytest fixtures for Warren Lanchonete backend tests.

Provides:
    db_session: In-memory SQLite async session (creates all tables).
    chroma_client: Ephemeral in-memory ChromaDB client.
    chroma_with_data: In-memory ChromaDB seeded with 3 Buffett passages.
    async_client: httpx AsyncClient wrapping the FastAPI app with DB override.
"""

from __future__ import annotations

import os

# Must be set before any app module is imported so config.py allows settings=None
os.environ.setdefault("TESTING", "1")

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import Base


# ── Database Fixture (in-memory SQLite) ──────────────────────────────────────


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory SQLite database with all tables for testing.

    Uses aiosqlite driver. Tables are created fresh for each test and
    dropped afterward to ensure test isolation.

    Yields:
        AsyncSession: Open async session connected to in-memory SQLite.
    """
    # Import all models to register with Base.metadata
    from app.models.company import Company  # noqa: F401
    from app.models.financial import Financial  # noqa: F401

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ── ChromaDB Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def chroma_client():
    """Create an ephemeral in-memory ChromaDB client.

    Uses chromadb.EphemeralClient() — data is not persisted to disk.
    Safe for parallel test runs.

    Returns:
        chromadb.Client: Ephemeral in-memory ChromaDB client.
    """
    try:
        import chromadb

        return chromadb.EphemeralClient()
    except ImportError:
        pytest.skip("chromadb not installed")


@pytest.fixture
def chroma_with_data(chroma_client):
    """ChromaDB client pre-seeded with 3 fake Buffett passages.

    Seeds the 'buffett_letters' collection with 3 documents so RAG service
    tests have data to query against without needing real PDFs.

    Args:
        chroma_client: The ephemeral ChromaDB client fixture.

    Returns:
        chromadb.Client: The same client, now with seeded data.
    """
    collection = chroma_client.get_or_create_collection("buffett_letters")
    collection.add(
        ids=["1992_letter_chunk_001", "2000_letter_chunk_002", "2007_letter_chunk_003"],
        documents=[
            "A truly wonderful business earns very high returns on the capital required for its operation.",
            "Price is what you pay. Value is what you get. This principle applies to Brazilian companies too.",
            "Our favorite holding period is forever. We look for durable competitive advantages.",
        ],
        metadatas=[
            {
                "year": 1992,
                "letter_type": "shareholder_letter",
                "topic": "",
                "source_file": "1992_letter.pdf",
            },
            {
                "year": 2000,
                "letter_type": "shareholder_letter",
                "topic": "",
                "source_file": "2000_letter.pdf",
            },
            {
                "year": 2007,
                "letter_type": "shareholder_letter",
                "topic": "",
                "source_file": "2007_letter.pdf",
            },
        ],
    )
    return chroma_client


# ── FastAPI Async Client Fixture ──────────────────────────────────────────────


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wrapping the FastAPI app with test DB and mocked services.

    Overrides:
        get_db: Returns the in-memory SQLite db_session fixture.
        get_portfolio_service: Returns a MagicMock (AI services mocked).
        get_rag_service: Returns a MagicMock.

    Args:
        db_session: In-memory SQLite session from db_session fixture.

    Yields:
        AsyncClient: Configured httpx client for making test requests.
    """
    from app.dependencies import get_db, get_portfolio_service, get_rag_service
    from app.main import app

    # Override get_db to use our in-memory SQLite session
    async def override_get_db():
        yield db_session

    # Override portfolio service with a mock (populated per-test)
    mock_portfolio_service = MagicMock()
    mock_portfolio_service.analyze = AsyncMock()

    def override_get_portfolio_service():
        return mock_portfolio_service

    # Override rag service with a mock
    def override_get_rag_service():
        return MagicMock()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_portfolio_service] = override_get_portfolio_service
    app.dependency_overrides[get_rag_service] = override_get_rag_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Expose the mock so tests can configure it
        client.app = app  # type: ignore[attr-defined]
        client.mock_portfolio_service = mock_portfolio_service  # type: ignore[attr-defined]
        yield client

    # Clean up overrides
    app.dependency_overrides.clear()
