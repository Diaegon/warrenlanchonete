"""Router for company data endpoints.

Provides read-only access to company and financial data stored in PostgreSQL.
No AI or RAG involvement — these endpoints are fast DB queries only.

Routes:
    GET /companies       — List all companies ordered by ticker.
    GET /companies/{ticker} — Get company detail with full financial history.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db
from app.models.company import Company
from app.schemas.company import CompanyDetailSchema, CompanySchema

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanySchema])
async def list_companies(db: AsyncSession = Depends(get_db)) -> list[Company]:
    """List all companies ordered by ticker symbol.

    Args:
        db: Async database session from dependency injection.

    Returns:
        List of CompanySchema objects ordered alphabetically by ticker.
    """
    stmt = select(Company).order_by(Company.ticker)
    result = await db.execute(stmt)
    companies = result.scalars().all()
    logger.info("companies.list", count=len(companies))
    return list(companies)


@router.get("/{ticker}", response_model=CompanyDetailSchema)
async def get_company(ticker: str, db: AsyncSession = Depends(get_db)) -> Company:
    """Get a company by ticker with its full financial history.

    Args:
        ticker: B3 ticker symbol (e.g. 'WEGE3').
        db: Async database session from dependency injection.

    Returns:
        CompanyDetailSchema with all financial records ordered by year descending.

    Raises:
        HTTPException(404): If the ticker is not found in the companies table.
    """
    stmt = (
        select(Company)
        .where(Company.ticker == ticker.upper())
        .options(selectinload(Company.financials))
    )
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if company is None:
        logger.warning("companies.not_found", ticker=ticker)
        raise HTTPException(
            status_code=404, detail=f"Company with ticker {ticker} not found"
        )

    logger.info("companies.detail", ticker=ticker)
    return company
