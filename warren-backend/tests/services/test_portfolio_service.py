"""Tests for app/services/portfolio_service.py.

TDD: tests written before implementation. All AI services are mocked.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_asset(ticker: str, asset_type: str, percentage: float):
    """Helper to create AssetInput instances."""
    from app.schemas.portfolio import AssetInput, AssetType
    return AssetInput(ticker=ticker, type=AssetType(asset_type), percentage=percentage)


def make_stock_analysis(score: float = 8.0, verdict: str = "APROVADO"):
    """Helper to create a mock StockAnalysis-like object."""
    return MagicMock(
        score=score,
        verdict=verdict,
        buffett_verdict="Ótima empresa.",
        buffett_citations=[],
        retail_adaptation_note="Adaptado para varejo.",
    )


def make_portfolio_summary(grade: str = "A", summary: str = "Portfólio excelente."):
    """Helper to create a mock PortfolioSummary-like object."""
    return MagicMock(portfolio_grade=grade, portfolio_summary=summary)


def make_company(ticker: str = "WEGE3", name: str = "WEG S.A.", sector: str = "Industrial"):
    """Helper to create a mock Company ORM instance."""
    company = MagicMock()
    company.ticker = ticker
    company.name = name
    company.sector = sector
    return company


def make_financial(
    roe: float = 28.5,
    margem_liquida: float = 15.2,
    cagr_lucro: float = 18.3,
    divida_ebitda: float = 0.4,
    year: int = 2024,
):
    """Helper to create a mock Financial ORM instance with Decimal-like fields."""
    fin = MagicMock()
    fin.year = year
    fin.roe = Decimal(str(roe))
    fin.margem_liquida = Decimal(str(margem_liquida))
    fin.cagr_lucro = Decimal(str(cagr_lucro))
    fin.divida_ebitda = Decimal(str(divida_ebitda))
    return fin


# ─── detect_alerts tests ──────────────────────────────────────────────────────

class TestDetectAlerts:
    """Tests for the detect_alerts pure function."""

    def test_no_tesouro_triggers_tesouro_zero(self) -> None:
        """TESOURO_ZERO alert when no tesouro in portfolio."""
        from app.services.portfolio_service import detect_alerts
        from app.schemas.portfolio import AlertType
        assets = [
            make_asset("WEGE3", "STOCK", 60.0),
            make_asset("PETR4", "STOCK", 40.0),
        ]
        alerts = detect_alerts(assets)
        alert_types = [a.type for a in alerts]
        assert AlertType.TESOURO_ZERO in alert_types

    def test_tesouro_low_triggers_when_below_5_percent(self) -> None:
        """TESOURO_LOW alert when tesouro is between 0 and 5 percent."""
        from app.services.portfolio_service import detect_alerts
        from app.schemas.portfolio import AlertType
        assets = [
            make_asset("WEGE3", "STOCK", 97.0),
            make_asset("TESOURO", "TESOURO", 3.0),
        ]
        alerts = detect_alerts(assets)
        alert_types = [a.type for a in alerts]
        assert AlertType.TESOURO_LOW in alert_types
        assert AlertType.TESOURO_ZERO not in alert_types

    def test_tesouro_at_5_percent_no_tesouro_alert(self) -> None:
        """No TESOURO alert when tesouro is >= 5 percent."""
        from app.services.portfolio_service import detect_alerts
        from app.schemas.portfolio import AlertType
        assets = [
            make_asset("WEGE3", "STOCK", 95.0),
            make_asset("TESOURO", "TESOURO", 5.0),
        ]
        alerts = detect_alerts(assets)
        alert_types = [a.type for a in alerts]
        assert AlertType.TESOURO_LOW not in alert_types
        assert AlertType.TESOURO_ZERO not in alert_types

    def test_single_stock_100_triggers(self) -> None:
        """SINGLE_STOCK_100 alert when one stock is >= 99.9%."""
        from app.services.portfolio_service import detect_alerts
        from app.schemas.portfolio import AlertType
        assets = [make_asset("WEGE3", "STOCK", 100.0)]
        alerts = detect_alerts(assets)
        alert_types = [a.type for a in alerts]
        assert AlertType.SINGLE_STOCK_100 in alert_types

    def test_commodity_heavy_triggers_over_40_percent(self) -> None:
        """COMMODITY_HEAVY alert when commodity tickers sum > 40%."""
        from app.services.portfolio_service import detect_alerts
        from app.schemas.portfolio import AlertType
        assets = [
            make_asset("PETR4", "STOCK", 30.0),
            make_asset("VALE3", "STOCK", 15.0),
            make_asset("WEGE3", "STOCK", 45.0),
            make_asset("TESOURO", "TESOURO", 10.0),
        ]
        alerts = detect_alerts(assets)
        alert_types = [a.type for a in alerts]
        assert AlertType.COMMODITY_HEAVY in alert_types

    def test_commodity_heavy_does_not_trigger_at_40_percent(self) -> None:
        """COMMODITY_HEAVY alert does NOT trigger when exactly at 40%."""
        from app.services.portfolio_service import detect_alerts
        from app.schemas.portfolio import AlertType
        assets = [
            make_asset("PETR4", "STOCK", 40.0),
            make_asset("WEGE3", "STOCK", 50.0),
            make_asset("TESOURO", "TESOURO", 10.0),
        ]
        alerts = detect_alerts(assets)
        alert_types = [a.type for a in alerts]
        assert AlertType.COMMODITY_HEAVY not in alert_types

    def test_over_concentrated_triggers_when_top2_over_80(self) -> None:
        """OVER_CONCENTRATED alert when top-2 assets sum > 80%."""
        from app.services.portfolio_service import detect_alerts
        from app.schemas.portfolio import AlertType
        assets = [
            make_asset("WEGE3", "STOCK", 50.0),
            make_asset("PETR4", "STOCK", 35.0),
            make_asset("TESOURO", "TESOURO", 15.0),
        ]
        alerts = detect_alerts(assets)
        alert_types = [a.type for a in alerts]
        assert AlertType.OVER_CONCENTRATED in alert_types

    def test_over_concentrated_does_not_trigger_at_80(self) -> None:
        """OVER_CONCENTRATED does NOT trigger when top-2 sum is exactly 80%."""
        from app.services.portfolio_service import detect_alerts
        from app.schemas.portfolio import AlertType
        assets = [
            make_asset("WEGE3", "STOCK", 40.0),
            make_asset("PETR4", "STOCK", 40.0),
            make_asset("TESOURO", "TESOURO", 20.0),
        ]
        alerts = detect_alerts(assets)
        alert_types = [a.type for a in alerts]
        assert AlertType.OVER_CONCENTRATED not in alert_types

    def test_multiple_alerts_at_once(self) -> None:
        """Multiple alerts can trigger simultaneously."""
        from app.services.portfolio_service import detect_alerts
        from app.schemas.portfolio import AlertType
        # PETR4 alone at 100% → TESOURO_ZERO + SINGLE_STOCK_100 + COMMODITY_HEAVY + OVER_CONCENTRATED
        assets = [make_asset("PETR4", "STOCK", 100.0)]
        alerts = detect_alerts(assets)
        alert_types = [a.type for a in alerts]
        assert AlertType.TESOURO_ZERO in alert_types
        assert AlertType.SINGLE_STOCK_100 in alert_types
        assert AlertType.COMMODITY_HEAVY in alert_types
        assert AlertType.OVER_CONCENTRATED not in alert_types  # need at least 2 for over-concentrated

    def test_tesouro_zero_message_is_humorous(self) -> None:
        """TESOURO_ZERO alert has the expected humorous message."""
        from app.services.portfolio_service import detect_alerts
        from app.schemas.portfolio import AlertType
        assets = [make_asset("WEGE3", "STOCK", 100.0)]
        alerts = detect_alerts(assets)
        tesouro_alerts = [a for a in alerts if a.type == AlertType.TESOURO_ZERO]
        assert len(tesouro_alerts) == 1
        assert "corajoso" in tesouro_alerts[0].message.lower() or "paraquedas" in tesouro_alerts[0].message.lower()

    def test_no_alerts_for_good_portfolio(self) -> None:
        """No alerts for a well-diversified portfolio."""
        from app.services.portfolio_service import detect_alerts
        assets = [
            make_asset("WEGE3", "STOCK", 35.0),
            make_asset("ITUB4", "STOCK", 30.0),
            make_asset("MXRF11", "FII", 10.0),
            make_asset("TESOURO", "TESOURO", 25.0),
        ]
        alerts = detect_alerts(assets)
        assert len(alerts) == 0


# ─── PortfolioService.analyze tests ──────────────────────────────────────────

class TestPortfolioServiceAnalyze:
    """Tests for PortfolioService.analyze() with mocked AI services."""

    def _make_service(self, rag_service=None, analysis_service=None):
        """Create PortfolioService with mocked dependencies."""
        from app.services.portfolio_service import PortfolioService
        rag = rag_service or AsyncMock()
        analysis = analysis_service or AsyncMock()
        return PortfolioService(rag_service=rag, analysis_service=analysis)

    def _make_request(self, assets):
        """Create PortfolioRequest from asset list."""
        from app.schemas.portfolio import PortfolioRequest
        return PortfolioRequest(assets=assets)

    async def test_analyze_raises_ticker_not_found_for_unknown_ticker(self) -> None:
        """analyze() raises TickerNotFoundError when stock ticker is not in DB."""
        from app.exceptions import TickerNotFoundError
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_db = AsyncMock(spec=AsyncSession)
        # DB returns no rows
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = self._make_service()
        request = self._make_request([make_asset("UNKNOWN1", "STOCK", 100.0)])

        with pytest.raises(TickerNotFoundError) as exc_info:
            await service.analyze(request, mock_db)
        assert exc_info.value.ticker == "UNKNOWN1"

    async def test_analyze_returns_correct_shape_with_mocked_ai(self) -> None:
        """analyze() returns PortfolioResponse with correct shape."""
        from app.schemas.portfolio import PortfolioResponse
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_db = AsyncMock(spec=AsyncSession)
        company = make_company("WEGE3")
        financial = make_financial()
        mock_result = MagicMock()
        mock_result.first.return_value = (company, financial)
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_rag = AsyncMock()
        mock_rag.retrieve = AsyncMock(return_value=[])

        mock_analysis = AsyncMock()
        mock_analysis.analyze_stock = AsyncMock(return_value=make_stock_analysis())
        mock_analysis.generate_portfolio_summary = AsyncMock(
            return_value=make_portfolio_summary()
        )

        service = self._make_service(rag_service=mock_rag, analysis_service=mock_analysis)
        request = self._make_request([make_asset("WEGE3", "STOCK", 100.0)])

        response = await service.analyze(request, mock_db)
        assert isinstance(response, PortfolioResponse)
        assert len(response.assets) == 1
        assert response.assets[0].ticker == "WEGE3"
        assert response.assets[0].type == "STOCK"

    async def test_analyze_partial_degradation_when_ai_fails(self) -> None:
        """analyze() returns degraded response for a stock when AI raises."""
        from app.schemas.portfolio import PortfolioResponse, StockAssetResponse
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_db = AsyncMock(spec=AsyncSession)
        company = make_company("WEGE3")
        financial = make_financial()
        mock_result = MagicMock()
        mock_result.first.return_value = (company, financial)
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_rag = AsyncMock()
        mock_rag.retrieve = AsyncMock(return_value=[])

        mock_analysis = AsyncMock()
        mock_analysis.analyze_stock = AsyncMock(side_effect=Exception("OpenAI failed"))
        mock_analysis.generate_portfolio_summary = AsyncMock(
            return_value=make_portfolio_summary()
        )

        service = self._make_service(rag_service=mock_rag, analysis_service=mock_analysis)
        request = self._make_request([make_asset("WEGE3", "STOCK", 100.0)])

        response = await service.analyze(request, mock_db)
        assert isinstance(response, PortfolioResponse)
        stock_assets = [a for a in response.assets if a.type == "STOCK"]
        assert len(stock_assets) == 1
        stock = stock_assets[0]
        assert isinstance(stock, StockAssetResponse)
        # Degraded response has score=0.0 and ATENÇÃO verdict
        assert stock.score == 0.0
        assert stock.verdict == "ATENÇÃO"

    async def test_analyze_fii_assets_get_fixed_verdict(self) -> None:
        """FII assets in analyze() get the fixed FII verdict."""
        from app.schemas.portfolio import FIIAssetResponse, PortfolioResponse
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_db = AsyncMock(spec=AsyncSession)
        # FII validation: ticker exists in DB
        mock_fii_result = MagicMock()
        mock_fii_result.scalar_one_or_none.return_value = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_fii_result)

        mock_rag = AsyncMock()
        mock_analysis = AsyncMock()
        mock_analysis.generate_portfolio_summary = AsyncMock(
            return_value=make_portfolio_summary()
        )

        service = self._make_service(rag_service=mock_rag, analysis_service=mock_analysis)
        request = self._make_request([make_asset("MXRF11", "FII", 100.0)])

        response = await service.analyze(request, mock_db)
        assert isinstance(response, PortfolioResponse)
        fii_assets = [a for a in response.assets if a.type == "FII"]
        assert len(fii_assets) == 1
        assert isinstance(fii_assets[0], FIIAssetResponse)
        assert "FII" in fii_assets[0].verdict

    async def test_analyze_raises_ticker_not_found_for_unknown_fii_ticker(self) -> None:
        """analyze() raises TickerNotFoundError when FII ticker is not in DB."""
        from app.exceptions import TickerNotFoundError
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_db = AsyncMock(spec=AsyncSession)
        # FII validation: ticker does NOT exist in DB
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = self._make_service()
        request = self._make_request([make_asset("XFII11", "FII", 100.0)])

        with pytest.raises(TickerNotFoundError):
            await service.analyze(request, mock_db)

    async def test_analyze_tesouro_assets_get_fixed_verdict(self) -> None:
        """TESOURO assets in analyze() get 'Capital seguro' verdict."""
        from app.schemas.portfolio import PortfolioResponse, TesouroAssetResponse
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_db = AsyncMock(spec=AsyncSession)
        # TESOURO validation: ticker exists in DB
        mock_tesouro_result = MagicMock()
        mock_tesouro_result.scalar_one_or_none.return_value = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_tesouro_result)

        mock_rag = AsyncMock()
        mock_analysis = AsyncMock()
        mock_analysis.generate_portfolio_summary = AsyncMock(
            return_value=make_portfolio_summary()
        )

        service = self._make_service(rag_service=mock_rag, analysis_service=mock_analysis)
        request = self._make_request([make_asset("TESOURO", "TESOURO", 100.0)])

        response = await service.analyze(request, mock_db)
        assert isinstance(response, PortfolioResponse)
        tesouro_assets = [a for a in response.assets if a.type == "TESOURO"]
        assert len(tesouro_assets) == 1
        assert isinstance(tesouro_assets[0], TesouroAssetResponse)
        assert tesouro_assets[0].verdict == "Capital seguro"

    async def test_analyze_raises_ticker_not_found_for_unknown_tesouro_ticker(self) -> None:
        """analyze() raises TickerNotFoundError when TESOURO ticker is not in DB."""
        from app.exceptions import TickerNotFoundError
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = self._make_service()
        request = self._make_request([make_asset("XTES11", "TESOURO", 100.0)])

        with pytest.raises(TickerNotFoundError):
            await service.analyze(request, mock_db)

    async def test_analyze_calls_rag_retrieve_for_each_stock(self) -> None:
        """analyze() calls rag_service.retrieve() once per STOCK asset."""
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_db = AsyncMock(spec=AsyncSession)
        company = make_company("WEGE3")
        financial = make_financial()
        mock_result = MagicMock()
        mock_result.first.return_value = (company, financial)
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_rag = AsyncMock()
        mock_rag.retrieve = AsyncMock(return_value=[])

        mock_analysis = AsyncMock()
        mock_analysis.analyze_stock = AsyncMock(return_value=make_stock_analysis())
        mock_analysis.generate_portfolio_summary = AsyncMock(
            return_value=make_portfolio_summary()
        )

        service = self._make_service(rag_service=mock_rag, analysis_service=mock_analysis)
        request = self._make_request([make_asset("WEGE3", "STOCK", 100.0)])

        await service.analyze(request, mock_db)
        mock_rag.retrieve.assert_called_once()

    async def test_analyze_degrades_when_company_exists_but_has_no_financials(self) -> None:
        """analyze() returns an explicit no-financial-data response for known stocks."""
        from app.schemas.portfolio import StockAssetResponse
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_db = AsyncMock(spec=AsyncSession)
        company = make_company("ALPA3", name="Alpargatas S.A.", sector="Consumo")
        # Outerjoin returns (company, None) when company has no financial rows
        mock_result = MagicMock()
        mock_result.first.return_value = (company, None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_rag = AsyncMock()
        mock_rag.retrieve = AsyncMock()
        mock_analysis = AsyncMock()
        mock_analysis.analyze_stock = AsyncMock()
        mock_analysis.generate_portfolio_summary = AsyncMock(return_value=make_portfolio_summary())

        service = self._make_service(rag_service=mock_rag, analysis_service=mock_analysis)
        request = self._make_request([make_asset("ALPA3", "STOCK", 100.0)])

        response = await service.analyze(request, mock_db)

        stock = response.assets[0]
        assert isinstance(stock, StockAssetResponse)
        assert stock.ticker == "ALPA3"
        assert stock.company_name == "Alpargatas S.A."
        assert stock.score == 0.0
        assert stock.verdict == "Dados financeiros indisponíveis"
        assert stock.financials.roe is None
        assert stock.financials.margem_liquida is None
        assert stock.financials.cagr_lucro is None
        assert stock.financials.divida_ebitda is None
        assert stock.buffett_citations == []
        mock_rag.retrieve.assert_not_called()
        mock_analysis.analyze_stock.assert_not_called()

    async def test_analyze_passes_uppercase_ticker_to_db_query(self) -> None:
        """analyze() passes the ticker unchanged (already uppercase per schema) to the DB query.

        The schema-level pattern validator (^[A-Z0-9]+$) now guarantees uppercase
        tickers at the API boundary. The service still uppercases defensively for
        internal callers, so we verify the DB WHERE clause receives the correct value.
        """
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_db = AsyncMock(spec=AsyncSession)
        company = make_company("WEGE3")
        financial = make_financial()
        mock_result = MagicMock()
        mock_result.first.return_value = (company, financial)
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_rag = AsyncMock()
        mock_rag.retrieve = AsyncMock(return_value=[])
        mock_analysis = AsyncMock()
        mock_analysis.analyze_stock = AsyncMock(return_value=make_stock_analysis())
        mock_analysis.generate_portfolio_summary = AsyncMock(return_value=make_portfolio_summary())

        service = self._make_service(rag_service=mock_rag, analysis_service=mock_analysis)
        request = self._make_request([make_asset("WEGE3", "STOCK", 100.0)])

        response = await service.analyze(request, mock_db)
        assert mock_db.execute.called
        stmt = mock_db.execute.call_args[0][0]
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        assert "WEGE3" in str(compiled)
