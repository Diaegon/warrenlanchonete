"""PDF generation service using Jinja2 and WeasyPrint.

Renders templates/report.html with the portfolio analysis data and produces
a PDF binary suitable for streaming to the HTTP client.

WeasyPrint is CPU-bound (500ms–2s). The generate() method runs it in a thread
pool executor to avoid blocking the async event loop.
"""
from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import structlog
import weasyprint
from jinja2 import Environment, FileSystemLoader

from app.exceptions import PDFGenerationError
from app.schemas.portfolio import PortfolioResponse

logger = structlog.get_logger(__name__)

# .resolve() normalises symlinks and makes the path absolute so it survives moves
_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


class PDFService:
    """Generates PDF reports from PortfolioResponse data.

    Renders the Jinja2 template at templates/report.html and uses WeasyPrint
    to produce a PDF binary.

    Example:
        service = PDFService()
        pdf_bytes = await service.generate(portfolio_response)
        # Stream to HTTP client
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf")
    """

    def __init__(self, templates_dir: str | Path | None = None) -> None:
        templates_path = Path(templates_dir) if templates_dir else _TEMPLATES_DIR
        if not templates_path.exists():
            raise RuntimeError(
                f"Templates directory not found: {templates_path}. "
                "Ensure templates/ exists at the project root."
            )
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(templates_path)),
            autoescape=True,
        )

    async def generate(self, portfolio_response: PortfolioResponse) -> bytes:
        """Render HTML template and convert to PDF.

        Jinja2 rendering is synchronous and fast (< 5ms). WeasyPrint rendering
        is CPU-bound and runs in a thread pool executor to avoid blocking the loop.

        Args:
            portfolio_response: Validated portfolio analysis response.

        Returns:
            PDF content as raw bytes.

        Raises:
            PDFGenerationError: If WeasyPrint raises any exception during rendering.
        """
        logger.info("pdf.generation.started", grade=portfolio_response.portfolio_grade)

        # Render Jinja2 template (fast, synchronous)
        template = self._jinja_env.get_template("report.html")
        context = portfolio_response.model_dump()
        context["analysis_date"] = date.today().strftime("%d/%m/%Y")
        html_content = template.render(**context)

        # WeasyPrint is CPU-bound — run in thread pool to avoid blocking the event loop
        try:
            loop = asyncio.get_running_loop()
            pdf_bytes: bytes = await loop.run_in_executor(
                None, lambda: weasyprint.HTML(string=html_content).write_pdf()
            )
        except Exception as exc:
            logger.error("pdf.generation.failed", error=str(exc))
            raise PDFGenerationError(f"WeasyPrint failed: {exc}") from exc

        logger.info("pdf.generation.completed", bytes=len(pdf_bytes))
        return pdf_bytes
