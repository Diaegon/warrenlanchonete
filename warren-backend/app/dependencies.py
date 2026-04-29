"""FastAPI dependency injection functions.

Provides:
    get_db: Async generator yielding an AsyncSession.
    get_rag_service: Returns the RAGService from app.state (set by lifespan).
    get_analysis_service: Returns the AnalysisService singleton.
    get_portfolio_service: Returns a PortfolioService with injected dependencies.
"""
from __future__ import annotations

import structlog
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db  # noqa: F401 — re-exported as single source of truth
from app.services.analysis_service import AnalysisService
from app.services.portfolio_service import PortfolioService

logger = structlog.get_logger(__name__)


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


def get_analysis_service() -> AnalysisService:
    """Return the AnalysisService singleton.

    Raises:
        HTTPException 503 if the singleton was not initialized (missing OPENAI_API_KEY).

    Returns:
        AnalysisService instance configured with settings.
    """
    if _analysis_service_singleton is None:
        raise HTTPException(
            status_code=503,
            detail="Analysis service not initialized. Check OPENAI_API_KEY configuration.",
        )
    return _analysis_service_singleton


def get_portfolio_service(
    rag_service=Depends(get_rag_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> PortfolioService:
    """Create and return a PortfolioService with injected dependencies.

    Args:
        rag_service: RAGService from app.state (via get_rag_service).
        analysis_service: AnalysisService singleton (via get_analysis_service).

    Returns:
        PortfolioService instance ready for use in route handlers.
    """
    return PortfolioService(rag_service=rag_service, analysis_service=analysis_service)
