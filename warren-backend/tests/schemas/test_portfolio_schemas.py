"""Tests for app/schemas/portfolio.py Pydantic schemas.

TDD: tests written before implementation.
"""
import pytest
from pydantic import ValidationError


class TestAssetInput:
    """Tests for AssetInput schema."""

    def test_valid_stock_asset(self) -> None:
        """AssetInput accepts a valid STOCK asset."""
        from app.schemas.portfolio import AssetInput, AssetType
        asset = AssetInput(ticker="WEGE3", type=AssetType.STOCK, percentage=50.0)
        assert asset.ticker == "WEGE3"
        assert asset.type == AssetType.STOCK
        assert asset.percentage == 50.0

    def test_valid_fii_asset(self) -> None:
        """AssetInput accepts a valid FII asset."""
        from app.schemas.portfolio import AssetInput, AssetType
        asset = AssetInput(ticker="MXRF11", type=AssetType.FII, percentage=25.0)
        assert asset.type == AssetType.FII

    def test_valid_tesouro_asset(self) -> None:
        """AssetInput accepts a valid TESOURO asset."""
        from app.schemas.portfolio import AssetInput, AssetType
        asset = AssetInput(ticker="TESOURO", type=AssetType.TESOURO, percentage=25.0)
        assert asset.type == AssetType.TESOURO

    def test_percentage_zero_raises(self) -> None:
        """percentage=0 raises ValidationError."""
        from app.schemas.portfolio import AssetInput, AssetType
        with pytest.raises(ValidationError):
            AssetInput(ticker="WEGE3", type=AssetType.STOCK, percentage=0)

    def test_percentage_above_100_raises(self) -> None:
        """percentage > 100 raises ValidationError."""
        from app.schemas.portfolio import AssetInput, AssetType
        with pytest.raises(ValidationError):
            AssetInput(ticker="WEGE3", type=AssetType.STOCK, percentage=100.1)

    def test_ticker_max_length_10(self) -> None:
        """Ticker with more than 10 characters raises ValidationError."""
        from app.schemas.portfolio import AssetInput, AssetType
        with pytest.raises(ValidationError):
            AssetInput(ticker="WAYTOOLONG123", type=AssetType.STOCK, percentage=50.0)

    def test_unknown_type_raises(self) -> None:
        """Unknown asset type raises ValidationError."""
        from app.schemas.portfolio import AssetInput
        with pytest.raises(ValidationError):
            AssetInput(ticker="WEGE3", type="UNKNOWN", percentage=50.0)


class TestPortfolioRequest:
    """Tests for PortfolioRequest schema with model_validator."""

    def test_valid_portfolio_all_three_types(self) -> None:
        """Valid portfolio with STOCK, FII, and TESOURO passes validation."""
        from app.schemas.portfolio import AssetInput, AssetType, PortfolioRequest
        request = PortfolioRequest(
            assets=[
                AssetInput(ticker="WEGE3", type=AssetType.STOCK, percentage=60.0),
                AssetInput(ticker="MXRF11", type=AssetType.FII, percentage=25.0),
                AssetInput(ticker="TESOURO", type=AssetType.TESOURO, percentage=15.0),
            ]
        )
        assert len(request.assets) == 3

    def test_percentages_sum_to_100_exactly(self) -> None:
        """Portfolio with percentages summing exactly to 100 passes."""
        from app.schemas.portfolio import AssetInput, AssetType, PortfolioRequest
        request = PortfolioRequest(
            assets=[
                AssetInput(ticker="WEGE3", type=AssetType.STOCK, percentage=50.0),
                AssetInput(ticker="PETR4", type=AssetType.STOCK, percentage=50.0),
            ]
        )
        assert request is not None

    def test_percentages_sum_99_5_raises(self) -> None:
        """Percentages summing to 99.5 raise ValidationError."""
        from app.schemas.portfolio import AssetInput, AssetType, PortfolioRequest
        with pytest.raises(ValidationError) as exc_info:
            PortfolioRequest(
                assets=[
                    AssetInput(ticker="WEGE3", type=AssetType.STOCK, percentage=50.0),
                    AssetInput(ticker="PETR4", type=AssetType.STOCK, percentage=49.5),
                ]
            )
        assert "sum" in str(exc_info.value).lower() or "100" in str(exc_info.value)

    def test_percentages_sum_100_005_passes(self) -> None:
        """Percentages summing to 100.005 (within 0.01 tolerance) pass."""
        from app.schemas.portfolio import AssetInput, AssetType, PortfolioRequest
        # 0.005 difference is within tolerance of 0.01
        request = PortfolioRequest(
            assets=[
                AssetInput(ticker="WEGE3", type=AssetType.STOCK, percentage=50.0),
                AssetInput(ticker="PETR4", type=AssetType.STOCK, percentage=50.005),
            ]
        )
        assert request is not None

    def test_empty_assets_raises(self) -> None:
        """Empty assets list raises ValidationError."""
        from app.schemas.portfolio import PortfolioRequest
        with pytest.raises(ValidationError):
            PortfolioRequest(assets=[])

    def test_percentages_sum_101_raises(self) -> None:
        """Percentages clearly over 100 raise ValidationError."""
        from app.schemas.portfolio import AssetInput, AssetType, PortfolioRequest
        with pytest.raises(ValidationError):
            PortfolioRequest(
                assets=[
                    AssetInput(ticker="WEGE3", type=AssetType.STOCK, percentage=60.0),
                    AssetInput(ticker="PETR4", type=AssetType.STOCK, percentage=41.0),
                ]
            )


class TestResponseSchemas:
    """Tests for portfolio response schemas."""

    def test_stock_asset_response_type_is_literal(self) -> None:
        """StockAssetResponse has type='STOCK' literal."""
        from app.schemas.portfolio import (
            BuffettCitation,
            FinancialSnapshot,
            StockAssetResponse,
        )
        response = StockAssetResponse(
            ticker="WEGE3",
            company_name="WEG S.A.",
            sector="Industrial",
            type="STOCK",
            percentage=50.0,
            score=8.5,
            verdict="APROVADO",
            financials=FinancialSnapshot(
                roe=28.5, margem_liquida=15.2, cagr_lucro=18.3, divida_ebitda=0.4
            ),
            buffett_verdict="Excelente empresa.",
            buffett_citations=[
                BuffettCitation(year=1992, passage="Some passage", relevance="Very relevant")
            ],
            retail_adaptation_note="Adapted for retail.",
        )
        assert response.type == "STOCK"

    def test_fii_asset_response_has_default_verdict(self) -> None:
        """FIIAssetResponse has default verdict text."""
        from app.schemas.portfolio import FIIAssetResponse
        response = FIIAssetResponse(ticker="MXRF11", type="FII", percentage=20.0)
        assert "FII" in response.verdict
        assert response.type == "FII"

    def test_tesouro_asset_response_has_default_verdict(self) -> None:
        """TesouroAssetResponse has default 'Capital seguro' verdict."""
        from app.schemas.portfolio import TesouroAssetResponse
        response = TesouroAssetResponse(ticker="TESOURO", type="TESOURO", percentage=10.0)
        assert response.verdict == "Capital seguro"
        assert response.type == "TESOURO"

    def test_asset_response_discriminated_union_stock(self) -> None:
        """AssetResponse discriminated union resolves STOCK correctly."""
        from app.schemas.portfolio import (
            AssetResponse,
            BuffettCitation,
            FinancialSnapshot,
            PortfolioResponse,
            StockAssetResponse,
        )
        from typing import get_args
        # Create a portfolio response with a stock
        stock = StockAssetResponse(
            ticker="WEGE3",
            company_name="WEG",
            sector="Industrial",
            type="STOCK",
            percentage=100.0,
            score=9.0,
            verdict="APROVADO",
            financials=FinancialSnapshot(roe=None, margem_liquida=None, cagr_lucro=None, divida_ebitda=None),
            buffett_verdict="Ótimo.",
            buffett_citations=[],
            retail_adaptation_note="",
        )
        response = PortfolioResponse(
            portfolio_grade="A",
            portfolio_summary="Excelente portfólio.",
            portfolio_alerts=[],
            assets=[stock],
        )
        assert response.assets[0].type == "STOCK"

    def test_portfolio_response_shape(self) -> None:
        """PortfolioResponse validates all fields."""
        from app.schemas.portfolio import (
            AlertType,
            FIIAssetResponse,
            PortfolioAlert,
            PortfolioResponse,
            TesouroAssetResponse,
        )
        response = PortfolioResponse(
            portfolio_grade="B+",
            portfolio_summary="Portfólio razoável.",
            portfolio_alerts=[
                PortfolioAlert(type=AlertType.TESOURO_LOW, message="Muito pouca renda fixa")
            ],
            assets=[
                FIIAssetResponse(ticker="MXRF11", type="FII", percentage=50.0),
                TesouroAssetResponse(ticker="TESOURO", type="TESOURO", percentage=50.0),
            ],
        )
        assert response.portfolio_grade == "B+"
        assert len(response.portfolio_alerts) == 1
        assert len(response.assets) == 2

    def test_financial_snapshot_all_none(self) -> None:
        """FinancialSnapshot allows all None fields."""
        from app.schemas.portfolio import FinancialSnapshot
        snap = FinancialSnapshot(
            roe=None, margem_liquida=None, cagr_lucro=None, divida_ebitda=None
        )
        assert snap.roe is None
