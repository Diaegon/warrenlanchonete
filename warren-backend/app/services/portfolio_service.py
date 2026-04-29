"""Portfolio analysis orchestrator service.

PortfolioService is the single entry point for portfolio analysis. It:
1. Splits assets into STOCKs, FIIs, and TESouros
2. Queries the DB for each STOCK company + latest financials
3. Runs concurrent per-STOCK analysis via asyncio.gather
4. Detects tone-of-voice alerts deterministically
5. Calls AnalysisService to generate a portfolio summary
6. Assembles and returns the PortfolioResponse

detect_alerts() is a pure function (no I/O) that implements the tone-of-voice
trigger system described in ARCHITECTURE.md §7.
"""
from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import TickerNotFoundError
from app.models.company import Company
from app.models.financial import Financial
from app.schemas.portfolio import (
    AlertType,
    AssetInput,
    AssetType,
    BuffettCitation,
    FIIAssetResponse,
    FinancialSnapshot,
    PortfolioAlert,
    PortfolioRequest,
    PortfolioResponse,
    StockAssetResponse,
    TesouroAssetResponse,
)

logger = structlog.get_logger(__name__)

# Commodity tickers used for COMMODITY_HEAVY trigger detection
COMMODITY_TICKERS: frozenset[str] = frozenset(
    {"PETR4", "PETR3", "VALE3", "CMIN3", "CSNA3", "GGBR4"}
)


def detect_alerts(assets: list[AssetInput]) -> list[PortfolioAlert]:
    """Detect tone-of-voice alerts from portfolio composition.

    This is a pure function — no I/O, fully deterministic. Alert detection
    runs on the raw AssetInput list (before AI analysis) so the alerts can
    be passed to the portfolio summary prompt.

    Alert rules:
        TESOURO_ZERO: No TESOURO assets in portfolio.
        TESOURO_LOW: TESOURO total > 0 but < 5%.
        SINGLE_STOCK_100: Any single STOCK >= 99.9% of portfolio.
        COMMODITY_HEAVY: Commodity tickers (PETR4, VALE3, etc.) sum > 40%.
        OVER_CONCENTRATED: Top-2 asset percentages sum > 80%.

    Args:
        assets: List of AssetInput items from the portfolio request.

    Returns:
        List of PortfolioAlert objects. May be empty.
    """
    alerts: list[PortfolioAlert] = []

    tesouro_pct = sum(a.percentage for a in assets if a.type == AssetType.TESOURO)
    stock_percentages: dict[str, float] = {
        a.ticker: a.percentage for a in assets if a.type == AssetType.STOCK
    }

    # TESOURO_ZERO takes precedence over TESOURO_LOW
    if tesouro_pct == 0:
        alerts.append(
            PortfolioAlert(
                type=AlertType.TESOURO_ZERO,
                message="Sem paraquedas? Corajoso.",
            )
        )
    elif tesouro_pct < 5:
        alerts.append(
            PortfolioAlert(
                type=AlertType.TESOURO_LOW,
                message="É muita coragem ter tão pouca renda fixa",
            )
        )

    # 100% single stock
    for ticker, pct in stock_percentages.items():
        if pct >= 99.9:
            alerts.append(
                PortfolioAlert(
                    type=AlertType.SINGLE_STOCK_100,
                    message="Colocou todos os ovos na mesma cesta, hein...",
                )
            )

    # High commodity concentration
    commodity_pct = sum(
        pct for ticker, pct in stock_percentages.items() if ticker in COMMODITY_TICKERS
    )
    if commodity_pct > 40:
        alerts.append(
            PortfolioAlert(
                type=AlertType.COMMODITY_HEAVY,
                message="Torce muito pro petróleo, né?",
            )
        )

    # Over-concentration: top-2 assets > 80% of portfolio
    all_pcts = sorted([a.percentage for a in assets], reverse=True)
    if len(all_pcts) >= 2 and (all_pcts[0] + all_pcts[1]) > 80:
        alerts.append(
            PortfolioAlert(
                type=AlertType.OVER_CONCENTRATED,
                message="Diversificação? Nunca ouvi falar.",
            )
        )

    return alerts


class PortfolioService:
    """Orchestrates the full portfolio analysis pipeline.

    Dependencies are injected via constructor so they can be mocked in tests.
    The AI agent will provide concrete implementations of rag_service and
    analysis_service. At this stage they are duck-typed (no Protocol enforcement).

    Args:
        rag_service: Object with async retrieve(ticker, sector, roe, divida_ebitda)
            method returning list[BuffettCitation].
        analysis_service: Object with async analyze_stock(company, financials,
            citations) and async generate_portfolio_summary(assets, alerts) methods.
    """

    def __init__(self, rag_service: object, analysis_service: object) -> None:
        self._rag = rag_service
        self._analysis = analysis_service

    async def analyze(
        self, request: PortfolioRequest, db: AsyncSession
    ) -> PortfolioResponse:
        """Run the full portfolio analysis pipeline.

        Args:
            request: Validated portfolio request with assets and percentages.
            db: Async SQLAlchemy session (injected by FastAPI Depends).

        Returns:
            PortfolioResponse with per-asset analysis, alerts, and portfolio grade.

        Raises:
            TickerNotFoundError: If any STOCK ticker is not in the companies table.
        """
        logger.info("portfolio.analysis.started", tickers=[a.ticker for a in request.assets])

        stocks = [a for a in request.assets if a.type == AssetType.STOCK]
        fiis = [a for a in request.assets if a.type == AssetType.FII]
        tesouros = [a for a in request.assets if a.type == AssetType.TESOURO]

        # Query DB for each stock. Missing companies are 404; missing financials
        # become explicit degraded asset responses below.
        stock_pairs: list[tuple[AssetInput, Company, Financial | None]] = []
        for asset in stocks:
            company, financial = await self._get_company_and_financials(asset.ticker, db)
            stock_pairs.append((asset, company, financial))

        # Validate FII and TESOURO tickers against the DB
        for asset in fiis:
            await self._validate_ticker_in_db(asset.ticker.upper(), "FII", db)
        for asset in tesouros:
            await self._validate_ticker_in_db(asset.ticker.upper(), "TESOURO", db)

        # Concurrent per-stock analysis
        stock_tasks = [
            self._analyze_single_stock(asset, company, financial)
            for asset, company, financial in stock_pairs
        ]
        stock_results = await asyncio.gather(*stock_tasks, return_exceptions=True)

        # Build stock asset responses, handling partial degradation
        stock_responses: list[StockAssetResponse] = []
        for idx, result in enumerate(stock_results):
            asset, company, financial = stock_pairs[idx]
            if financial is None:
                logger.warning(
                    "portfolio.stock.financials_missing",
                    ticker=asset.ticker,
                )
                stock_responses.append(_make_missing_financials_stock_response(asset, company))
                continue
            if isinstance(result, BaseException):
                logger.warning(
                    "portfolio.stock.analysis.failed",
                    ticker=asset.ticker,
                    error=str(result),
                )
                stock_responses.append(
                    _make_degraded_stock_response(asset, company, financial)
                )
            else:
                stock_responses.append(result)

        # FII and TESOURO — fixed responses, no AI
        fii_responses = [
            FIIAssetResponse(ticker=a.ticker, type="FII", percentage=a.percentage)
            for a in fiis
        ]
        tesouro_responses = [
            TesouroAssetResponse(ticker=a.ticker, type="TESOURO", percentage=a.percentage)
            for a in tesouros
        ]

        # Detect tone-of-voice alerts
        alerts = detect_alerts(request.assets)

        # Assemble all assets in original order
        all_asset_responses = (
            _reorder_assets(request.assets, stock_responses, fii_responses, tesouro_responses)
        )

        # Portfolio summary from AI
        logger.info("portfolio.summary.started")
        summary = await self._analysis.generate_portfolio_summary(all_asset_responses, alerts)
        logger.info("portfolio.summary.completed", grade=summary.portfolio_grade)

        return PortfolioResponse(
            portfolio_grade=summary.portfolio_grade,
            portfolio_summary=summary.portfolio_summary,
            portfolio_alerts=alerts,
            assets=all_asset_responses,
        )

    async def _get_company_and_financials(
        self, ticker: str, db: AsyncSession
    ) -> tuple[Company, Financial | None]:
        """Query company and its most recent financial record.

        Uses an outer join so that a company with no financials returns
        (company, None) rather than no rows, allowing a clear error message
        that distinguishes "ticker not found" from "no financial data yet".

        Args:
            ticker: B3 ticker symbol to look up (normalized to uppercase).
            db: Async database session.

        Returns:
            Tuple of (Company, Financial | None) for the most recent year.

        Raises:
            TickerNotFoundError: If the ticker is not in the companies table.
        """
        ticker = ticker.upper()
        stmt = (
            select(Company, Financial)
            .outerjoin(Financial, Company.id == Financial.company_id)
            .where(Company.ticker == ticker)
            .order_by(Financial.year.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        row = result.first()
        if row is None:
            raise TickerNotFoundError(ticker)
        company, financial = row
        return company, financial

    async def _validate_ticker_in_db(
        self, ticker: str, asset_type: str, db: AsyncSession
    ) -> None:
        """Verify a ticker exists in the companies table with the given asset_type.

        Args:
            ticker: B3 ticker symbol (already uppercased by caller).
            asset_type: Expected asset type ('FII' or 'TESOURO').
            db: Async database session.

        Raises:
            TickerNotFoundError: If no company with this ticker and asset_type exists.
        """
        stmt = select(Company.id).where(
            Company.ticker == ticker,
            Company.asset_type == asset_type,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise TickerNotFoundError(ticker)

    async def _analyze_single_stock(
        self,
        asset: AssetInput,
        company: Company,
        financial: Financial | None,
    ) -> StockAssetResponse:
        """Analyze a single stock using RAG retrieval and AI analysis.

        Args:
            asset: The original AssetInput from the portfolio request.
            company: Company ORM instance.
            financial: Latest Financial ORM instance.

        Returns:
            StockAssetResponse with AI-generated analysis.
        """
        logger.info("portfolio.stock.analysis.started", ticker=asset.ticker)

        if financial is None:
            return _make_missing_financials_stock_response(asset, company)

        # RAG retrieval
        roe_val = float(financial.roe) if financial.roe is not None else 0.0
        de_val = float(financial.divida_ebitda) if financial.divida_ebitda is not None else 0.0
        citations: list[BuffettCitation] = await self._rag.retrieve(
            ticker=asset.ticker,
            sector=company.sector or "",
            roe=roe_val,
            divida_ebitda=de_val,
        )

        # AI analysis
        analysis = await self._analysis.analyze_stock(company, financial, citations)

        logger.info("portfolio.stock.analysis.completed", ticker=asset.ticker, score=analysis.score)

        return StockAssetResponse(
            ticker=asset.ticker,
            company_name=company.name,
            sector=company.sector,
            type="STOCK",
            percentage=asset.percentage,
            score=analysis.score,
            verdict=analysis.verdict,
            financials=FinancialSnapshot(
                year=financial.year,
                roe=float(financial.roe) if financial.roe is not None else None,
                margem_liquida=float(financial.margem_liquida) if financial.margem_liquida is not None else None,
                cagr_lucro=float(financial.cagr_lucro) if financial.cagr_lucro is not None else None,
                divida_ebitda=float(financial.divida_ebitda) if financial.divida_ebitda is not None else None,
            ),
            buffett_verdict=analysis.buffett_verdict,
            buffett_citations=analysis.buffett_citations,
            retail_adaptation_note=analysis.retail_adaptation_note,
        )


def _make_degraded_stock_response(
    asset: AssetInput, company: Company, financial: Financial
) -> StockAssetResponse:
    """Create a degraded StockAssetResponse when AI analysis fails.

    Args:
        asset: The original AssetInput.
        company: Company ORM instance (for name/sector).
        financial: Latest Financial ORM instance (for metrics).

    Returns:
        StockAssetResponse with score=0.0 and a degraded message.
    """
    return StockAssetResponse(
        ticker=asset.ticker,
        company_name=company.name,
        sector=company.sector,
        type="STOCK",
        percentage=asset.percentage,
        score=0.0,
        verdict="ATENÇÃO",
        financials=FinancialSnapshot(
            year=financial.year,
            roe=float(financial.roe) if financial.roe is not None else None,
            margem_liquida=float(financial.margem_liquida) if financial.margem_liquida is not None else None,
            cagr_lucro=float(financial.cagr_lucro) if financial.cagr_lucro is not None else None,
            divida_ebitda=float(financial.divida_ebitda) if financial.divida_ebitda is not None else None,
        ),
        buffett_verdict="Análise indisponível no momento. Tente novamente.",
        buffett_citations=[],
        retail_adaptation_note="",
    )


def _make_missing_financials_stock_response(
    asset: AssetInput, company: Company
) -> StockAssetResponse:
    """Create a StockAssetResponse when company metadata exists but fundamentals do not."""
    return StockAssetResponse(
        ticker=asset.ticker,
        company_name=company.name,
        sector=company.sector,
        type="STOCK",
        percentage=asset.percentage,
        score=0.0,
        verdict="Dados financeiros indisponíveis",
        financials=FinancialSnapshot(
            year=None,
            roe=None,
            margem_liquida=None,
            cagr_lucro=None,
            divida_ebitda=None,
        ),
        buffett_verdict=(
            "Ainda não temos fundamentos suficientes para avaliar este ativo "
            "com os critérios da Warren Lanchonete."
        ),
        buffett_citations=[],
        retail_adaptation_note=(
            "O ticker existe na base da B3, mas os dados financeiros anuais "
            "ainda não foram carregados."
        ),
    )


def _reorder_assets(
    original_assets: list[AssetInput],
    stock_responses: list[StockAssetResponse],
    fii_responses: list[FIIAssetResponse],
    tesouro_responses: list[TesouroAssetResponse],
) -> list:
    """Reorder asset responses to match the original request order.

    Args:
        original_assets: Original AssetInput list preserving user's order.
        stock_responses: Analyzed stock responses (same order as stocks in request).
        fii_responses: FII responses.
        tesouro_responses: TESOURO responses.

    Returns:
        List of asset responses in the same order as the original request.
    """
    stock_by_ticker = {r.ticker: r for r in stock_responses}
    fii_by_ticker = {r.ticker: r for r in fii_responses}
    tesouro_by_ticker = {r.ticker: r for r in tesouro_responses}

    ordered = []
    for asset in original_assets:
        if asset.type == AssetType.STOCK:
            ordered.append(stock_by_ticker[asset.ticker])
        elif asset.type == AssetType.FII:
            ordered.append(fii_by_ticker[asset.ticker])
        else:
            ordered.append(tesouro_by_ticker[asset.ticker])
    return ordered
