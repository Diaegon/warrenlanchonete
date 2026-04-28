"""Tests for app/services/pdf_service.py.

TDD: WeasyPrint is mocked — no actual PDF is generated in these tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_portfolio_response():
    """Build a minimal but valid PortfolioResponse for testing."""
    from app.schemas.portfolio import (
        AlertType,
        FIIAssetResponse,
        PortfolioAlert,
        PortfolioResponse,
        StockAssetResponse,
        FinancialSnapshot,
        BuffettCitation,
        TesouroAssetResponse,
    )
    return PortfolioResponse(
        portfolio_grade="B+",
        portfolio_summary="Portfólio razoável.",
        portfolio_alerts=[
            PortfolioAlert(type=AlertType.TESOURO_LOW, message="Pouca renda fixa")
        ],
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
                    BuffettCitation(year=1992, passage="Some passage", relevance="Relevant")
                ],
                retail_adaptation_note="Adapted note.",
            ),
            FIIAssetResponse(ticker="MXRF11", type="FII", percentage=25.0),
            TesouroAssetResponse(ticker="TESOURO", type="TESOURO", percentage=15.0),
        ],
    )


class TestPDFService:
    """Tests for PDFService.generate()."""

    def test_generate_returns_bytes(self) -> None:
        """generate() returns bytes when WeasyPrint succeeds."""
        from app.services.pdf_service import PDFService

        mock_html_obj = MagicMock()
        mock_html_obj.write_pdf.return_value = b"%PDF-1.4 fake pdf content"

        with patch("app.services.pdf_service.weasyprint") as mock_wp:
            mock_wp.HTML.return_value = mock_html_obj
            service = PDFService()
            result = service.generate(_make_portfolio_response())

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_raises_pdf_generation_error_on_weasyprint_exception(self) -> None:
        """generate() raises PDFGenerationError when WeasyPrint raises."""
        from app.exceptions import PDFGenerationError
        from app.services.pdf_service import PDFService

        mock_html_obj = MagicMock()
        mock_html_obj.write_pdf.side_effect = Exception("WeasyPrint internal error")

        with patch("app.services.pdf_service.weasyprint") as mock_wp:
            mock_wp.HTML.return_value = mock_html_obj
            service = PDFService()
            with pytest.raises(PDFGenerationError):
                service.generate(_make_portfolio_response())

    def test_generate_calls_weasyprint_html_with_string(self) -> None:
        """generate() passes rendered HTML string to weasyprint.HTML."""
        from app.services.pdf_service import PDFService

        mock_html_obj = MagicMock()
        mock_html_obj.write_pdf.return_value = b"fake pdf"

        with patch("app.services.pdf_service.weasyprint") as mock_wp:
            mock_wp.HTML.return_value = mock_html_obj
            service = PDFService()
            service.generate(_make_portfolio_response())

        # Verify weasyprint.HTML was called with a string keyword arg
        call_kwargs = mock_wp.HTML.call_args
        assert call_kwargs is not None
        # HTML should be called with string= kwarg
        assert "string" in call_kwargs.kwargs or len(call_kwargs.args) > 0

    def test_generate_includes_grade_in_html(self) -> None:
        """The rendered HTML includes the portfolio grade."""
        from app.services.pdf_service import PDFService

        rendered_html = None

        def capture_html(**kwargs):
            nonlocal rendered_html
            rendered_html = kwargs.get("string", "")
            mock_obj = MagicMock()
            mock_obj.write_pdf.return_value = b"fake pdf"
            return mock_obj

        with patch("app.services.pdf_service.weasyprint") as mock_wp:
            mock_wp.HTML.side_effect = capture_html
            service = PDFService()
            service.generate(_make_portfolio_response())

        assert rendered_html is not None
        assert "B+" in rendered_html
