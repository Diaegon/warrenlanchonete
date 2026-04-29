"""Tests for app/routers/portfolio.py.

TDD: PortfolioService is fully mocked via dependency override.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from httpx import AsyncClient


def _make_portfolio_response():
    """Build a minimal but valid PortfolioResponse for mock returns."""
    from app.schemas.portfolio import (
        BuffettCitation,
        FIIAssetResponse,
        FinancialSnapshot,
        PortfolioResponse,
        StockAssetResponse,
        TesouroAssetResponse,
    )

    return PortfolioResponse(
        portfolio_grade="B+",
        portfolio_summary="Portfólio razoável.",
        portfolio_alerts=[],
        assets=[
            StockAssetResponse(
                ticker="WEGE3",
                company_name="WEG S.A.",
                sector="Industrial",
                type="STOCK",
                percentage=60.0,
                score=8.5,
                verdict="APROVADO",
                financials=FinancialSnapshot(
                    roe=28.5, margem_liquida=15.2, cagr_lucro=18.3, divida_ebitda=0.4
                ),
                buffett_verdict="Empresa sólida.",
                buffett_citations=[
                    BuffettCitation(
                        year=1992, passage="Some passage", relevance="Relevant"
                    )
                ],
                retail_adaptation_note="Adapted note.",
            ),
            FIIAssetResponse(ticker="MXRF11", type="FII", percentage=25.0),
            TesouroAssetResponse(ticker="TESOURO", type="TESOURO", percentage=15.0),
        ],
    )


_VALID_REQUEST = {
    "assets": [
        {"ticker": "WEGE3", "type": "STOCK", "percentage": 60.0},
        {"ticker": "MXRF11", "type": "FII", "percentage": 25.0},
        {"ticker": "TESOURO", "type": "TESOURO", "percentage": 15.0},
    ]
}


class TestPortfolioAnalyze:
    """Tests for POST /api/portfolio/analyze."""

    async def test_valid_request_returns_200(self, async_client: AsyncClient) -> None:
        """Valid portfolio request returns 200 with PortfolioResponse shape."""
        async_client.mock_portfolio_service.analyze = AsyncMock(
            return_value=_make_portfolio_response()
        )
        response = await async_client.post(
            "/api/portfolio/analyze", json=_VALID_REQUEST
        )
        assert response.status_code == 200
        data = response.json()
        assert "portfolio_grade" in data
        assert "portfolio_summary" in data
        assert "assets" in data
        assert data["portfolio_grade"] == "B+"

    async def test_invalid_percentages_returns_422(
        self, async_client: AsyncClient
    ) -> None:
        """Request with percentages not summing to 100 returns 422."""
        bad_request = {
            "assets": [
                {"ticker": "WEGE3", "type": "STOCK", "percentage": 60.0},
                {"ticker": "PETR4", "type": "STOCK", "percentage": 30.0},
                # Missing 10%, total = 90%
            ]
        }
        response = await async_client.post("/api/portfolio/analyze", json=bad_request)
        assert response.status_code == 422

    async def test_unknown_ticker_returns_404(self, async_client: AsyncClient) -> None:
        """PortfolioService raising TickerNotFoundError returns 404."""
        from app.exceptions import TickerNotFoundError

        async_client.mock_portfolio_service.analyze = AsyncMock(
            side_effect=TickerNotFoundError("UNKNOWN1")
        )
        response = await async_client.post(
            "/api/portfolio/analyze", json=_VALID_REQUEST
        )
        assert response.status_code == 404
        data = response.json()
        assert "UNKNOWN1" in data["detail"]

    async def test_openai_unavailable_returns_503(
        self, async_client: AsyncClient
    ) -> None:
        """PortfolioService raising OpenAIUnavailableError returns 503."""
        from app.exceptions import OpenAIUnavailableError

        async_client.mock_portfolio_service.analyze = AsyncMock(
            side_effect=OpenAIUnavailableError("OpenAI down")
        )
        response = await async_client.post(
            "/api/portfolio/analyze", json=_VALID_REQUEST
        )
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data

    async def test_format_pdf_returns_pdf_content_type(
        self, async_client: AsyncClient
    ) -> None:
        """?format=pdf returns application/pdf content type."""
        from unittest.mock import patch

        async_client.mock_portfolio_service.analyze = AsyncMock(
            return_value=_make_portfolio_response()
        )

        with patch("app.routers.portfolio.PDFService") as mock_pdf_cls:
            mock_pdf_instance = mock_pdf_cls.return_value
            mock_pdf_instance.generate = AsyncMock(
                return_value=b"%PDF-1.4 fake content"
            )

            response = await async_client.post(
                "/api/portfolio/analyze?format=pdf", json=_VALID_REQUEST
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

    async def test_analyze_returns_503_on_timeout(
        self, async_client: AsyncClient
    ) -> None:
        """asyncio.TimeoutError from wait_for returns 503 with 'timed out' detail."""
        import asyncio
        from unittest.mock import patch

        with patch(
            "app.routers.portfolio.asyncio.wait_for", side_effect=asyncio.TimeoutError()
        ):
            response = await async_client.post(
                "/api/portfolio/analyze", json=_VALID_REQUEST
            )

        assert response.status_code == 503
        assert "timed out" in response.json()["detail"].lower()

    async def test_empty_assets_returns_422(self, async_client: AsyncClient) -> None:
        """Empty assets list returns 422."""
        response = await async_client.post(
            "/api/portfolio/analyze", json={"assets": []}
        )
        assert response.status_code == 422

    async def test_unknown_asset_type_returns_422(
        self, async_client: AsyncClient
    ) -> None:
        """Unknown asset type returns 422."""
        bad_request = {
            "assets": [
                {"ticker": "WEGE3", "type": "UNKNOWN_TYPE", "percentage": 100.0},
            ]
        }
        response = await async_client.post("/api/portfolio/analyze", json=bad_request)
        assert response.status_code == 422
