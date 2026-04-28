"""PDF generation service using Jinja2 and WeasyPrint.

Renders templates/report.html with the portfolio analysis data and produces
a PDF binary suitable for streaming to the HTTP client.

This service is CPU-bound (WeasyPrint renders to PDF synchronously).
For v1 it is called synchronously from the router; if profiling reveals
event-loop blocking under load, wrap with run_in_executor.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import structlog
import weasyprint
from jinja2 import Environment, FileSystemLoader

from app.exceptions import PDFGenerationError
from app.schemas.portfolio import PortfolioResponse

logger = structlog.get_logger(__name__)

# Resolve templates directory relative to this file's package root
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


class PDFService:
    """Generates PDF reports from PortfolioResponse data.

    Renders the Jinja2 template at templates/report.html and uses WeasyPrint
    to produce a PDF binary.

    Example:
        service = PDFService()
        pdf_bytes = service.generate(portfolio_response)
        # Stream to HTTP client
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf")
    """

    def __init__(self, templates_dir: str | Path | None = None) -> None:
        templates_path = Path(templates_dir) if templates_dir else _TEMPLATES_DIR
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(templates_path)),
            autoescape=True,
        )

    def generate(self, portfolio_response: PortfolioResponse) -> bytes:
        """Render HTML template and convert to PDF.

        Args:
            portfolio_response: Validated portfolio analysis response.

        Returns:
            PDF content as raw bytes.

        Raises:
            PDFGenerationError: If WeasyPrint raises any exception during rendering.
        """
        logger.info("pdf.generation.started", grade=portfolio_response.portfolio_grade)

        # Render Jinja2 template
        template = self._jinja_env.get_template("report.html")
        context = portfolio_response.model_dump()
        context["analysis_date"] = date.today().strftime("%d/%m/%Y")
        html_content = template.render(**context)

        # Convert to PDF
        try:
            pdf_bytes: bytes = weasyprint.HTML(string=html_content).write_pdf()
        except Exception as exc:
            logger.error("pdf.generation.failed", error=str(exc))
            raise PDFGenerationError(f"WeasyPrint failed: {exc}") from exc

        logger.info("pdf.generation.completed", bytes=len(pdf_bytes))
        return pdf_bytes
