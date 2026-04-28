"""Router for portfolio analysis endpoint.

The single route delegates entirely to PortfolioService. The optional ?format=pdf
query parameter triggers PDF generation via PDFService.

Routes:
    POST /portfolio/analyze — Analyze a portfolio request.
"""
from __future__ import annotations

import io

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_portfolio_service
from app.schemas.portfolio import PortfolioRequest, PortfolioResponse
from app.services.pdf_service import PDFService
from app.services.portfolio_service import PortfolioService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/analyze", response_model=None)
async def analyze_portfolio(
    request: PortfolioRequest,
    format: str | None = Query(default=None, description="Response format. Use 'pdf' for PDF export."),
    db: AsyncSession = Depends(get_db),
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
):
    """Analyze a portfolio using Buffett's criteria.

    Validates the portfolio request, delegates to PortfolioService for AI
    analysis, and returns either JSON or PDF depending on the format parameter.

    Args:
        request: Validated portfolio with assets and percentages summing to 100.
        format: Optional format parameter. Pass 'pdf' for PDF export.
        db: Async database session.
        portfolio_service: Injected portfolio analysis service.

    Returns:
        PortfolioResponse as JSON, or StreamingResponse with PDF bytes.

    Raises:
        HTTPException(404): If a STOCK ticker is not found (via exception handler).
        HTTPException(503): If OpenAI is unavailable (via exception handler).
    """
    logger.info("portfolio.analyze.request", asset_count=len(request.assets))

    response: PortfolioResponse = await portfolio_service.analyze(request, db)

    if format and format.lower() == "pdf":
        logger.info("portfolio.pdf.export", grade=response.portfolio_grade)
        pdf_service = PDFService()
        pdf_bytes = pdf_service.generate(response)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="warren_report.pdf"'},
        )

    return response
