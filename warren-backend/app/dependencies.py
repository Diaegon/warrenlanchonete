"""FastAPI dependency injection functions.

Provides:
    get_db: Async generator yielding an AsyncSession.
    get_rag_service: Returns the RAGService from app.state (set by lifespan).
    get_analysis_service: Returns the AnalysisService singleton.
    get_portfolio_service: Returns a PortfolioService with injected dependencies.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

import structlog
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db as _get_db_from_session
from app.services.analysis_service import AnalysisService
from app.services.portfolio_service import PortfolioService

logger = structlog.get_logger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependency injection.

    Wraps the session generator from app.db.session. Tests override this
    dependency with the in-memory SQLite fixture.

    Yields:
        AsyncSession: Open async SQLAlchemy session.
    """
    async for session in _get_db_from_session():
        yield session


def get_rag_service(request: Request):
    """Return the RAGService instance from application state.

    Set by the lifespan context manager in app/main.py during startup.
    Returns None if not yet initialized (app is degraded).

    Args:
        request: FastAPI request with access to app.state.

    Returns:
        RAGService instance or None.
    """
    return request.app.state.rag_service


# Module-level AnalysisService singleton — initialized once, reused for all requests.
# Guards against missing settings in test environment.
_analysis_service_singleton: AnalysisService | None = None

if settings is not None:
    _analysis_service_singleton = AnalysisService(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL,
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
    )


def get_analysis_service() -> AnalysisService | None:
    """Return the AnalysisService singleton.

    Returns:
        AnalysisService instance configured with settings, or None if
        settings are unavailable (test environment without .env).
    """
    return _analysis_service_singleton


def get_portfolio_service(
    rag_service=Depends(get_rag_service),
    analysis_service=Depends(get_analysis_service),
) -> PortfolioService:
    """Create and return a PortfolioService with injected dependencies.

    Args:
        rag_service: RAGService from app.state (via get_rag_service).
        analysis_service: AnalysisService singleton (via get_analysis_service).

    Returns:
        PortfolioService instance ready for use in route handlers.
    """
    return PortfolioService(rag_service=rag_service, analysis_service=analysis_service)
