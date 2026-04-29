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
            FinancialSnapshot,
            PortfolioResponse,
            StockAssetResponse,
        )
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


class TestAssetInputTickerPattern:
    """Tests for the ticker pattern validator on AssetInput."""

    def test_lowercase_ticker_raises_validation_error(self) -> None:
        """Lowercase tickers are rejected — B3 tickers are always uppercase."""
        from app.schemas.portfolio import AssetInput, AssetType
        with pytest.raises(ValidationError):
            AssetInput(ticker="wege3", type=AssetType.STOCK, percentage=100)

    def test_ticker_with_special_chars_raises_validation_error(self) -> None:
        """Tickers with hyphens, underscores, or spaces are rejected."""
        from app.schemas.portfolio import AssetInput, AssetType
        for bad_ticker in ["WEG-3", "WEG_3", "WEG 3", "WEG.3"]:
            with pytest.raises(ValidationError):
                AssetInput(ticker=bad_ticker, type=AssetType.STOCK, percentage=100)

    def test_uppercase_alphanumeric_ticker_valid(self) -> None:
        """Standard B3 tickers (uppercase + digits) are accepted."""
        from app.schemas.portfolio import AssetInput, AssetType
        for good_ticker in ["WEGE3", "MXRF11", "TESOURO", "PETR4", "BBAS3"]:
            asset = AssetInput(ticker=good_ticker, type=AssetType.STOCK, percentage=100)
            assert asset.ticker == good_ticker


class TestPortfolioGradeValidation:
    """Tests for portfolio_grade field validation in PortfolioResponse."""

    def _make_fii_response(self) -> dict:
        return {
            "portfolio_summary": "Teste.",
            "portfolio_alerts": [],
            "assets": [{"ticker": "MXRF11", "type": "FII", "percentage": 100.0}],
        }

    def test_valid_grades_are_accepted(self) -> None:
        """All valid letter grades are accepted by PortfolioResponse."""
        from app.schemas.portfolio import PortfolioResponse
        valid_grades = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]
        for grade in valid_grades:
            resp = PortfolioResponse(portfolio_grade=grade, **self._make_fii_response())
            assert resp.portfolio_grade == grade

    def test_grade_with_trailing_whitespace_is_stripped(self) -> None:
        """portfolio_grade with surrounding whitespace is stripped to its base value."""
        from app.schemas.portfolio import PortfolioResponse
        resp = PortfolioResponse(portfolio_grade="  B+  ", **self._make_fii_response())
        assert resp.portfolio_grade == "B+"

    def test_invalid_grade_raises_validation_error(self) -> None:
        """An out-of-scale grade like 'A+' raises ValidationError."""
        from app.schemas.portfolio import PortfolioResponse
        with pytest.raises(ValidationError):
            PortfolioResponse(portfolio_grade="A+", **self._make_fii_response())

    def test_empty_grade_raises_validation_error(self) -> None:
        """An empty string grade raises ValidationError."""
        from app.schemas.portfolio import PortfolioResponse
        with pytest.raises(ValidationError):
            PortfolioResponse(portfolio_grade="", **self._make_fii_response())


class TestPortfolioSummaryGradeValidation:
    """Tests for portfolio_grade in the internal PortfolioSummary model."""

    def test_valid_grade_accepted(self) -> None:
        """PortfolioSummary accepts a valid grade."""
        from app.services.analysis_service import PortfolioSummary
        s = PortfolioSummary(portfolio_grade="B+", portfolio_summary="Ok.")
        assert s.portfolio_grade == "B+"

    def test_grade_with_whitespace_is_stripped(self) -> None:
        """PortfolioSummary strips whitespace from grade before validation."""
        from app.services.analysis_service import PortfolioSummary
        s = PortfolioSummary(portfolio_grade=" A ", portfolio_summary="Ok.")
        assert s.portfolio_grade == "A"

    def test_invalid_grade_raises_validation_error(self) -> None:
        """PortfolioSummary rejects an invalid grade."""
        from app.services.analysis_service import PortfolioSummary
        with pytest.raises(ValidationError):
            PortfolioSummary(portfolio_grade="Z", portfolio_summary="Ok.")
