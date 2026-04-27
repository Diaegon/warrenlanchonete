"""Custom exception hierarchy for Warren Lanchonete backend.

All domain exceptions inherit from WarrenBaseError so callers can catch
the entire hierarchy with a single except clause if needed.

Usage:
    from app.exceptions import TickerNotFoundError, OpenAIUnavailableError

    # In a service:
    raise TickerNotFoundError("WEGE3")

    # In main.py exception handler:
    @app.exception_handler(TickerNotFoundError)
    async def handle(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})
"""


class WarrenBaseError(Exception):
    """Base class for all Warren Lanchonete domain exceptions."""


class TickerNotFoundError(WarrenBaseError):
    """Raised when a STOCK ticker is not found in the companies table.

    Attributes:
        ticker: The ticker symbol that was not found.
    """

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        super().__init__(f"Ticker {ticker} not found in database")


class OpenAIUnavailableError(WarrenBaseError):
    """Raised when the OpenAI API is unreachable or returns an invalid response.

    Mapped to HTTP 503 Service Unavailable.
    """


class RAGEmptyResultError(WarrenBaseError):
    """Raised when ChromaDB returns no results for a retrieval query.

    NOTE: Not raised in v1 — RAGService returns an empty list instead.
    Reserved for future use when callers need to distinguish this condition.
    """


class PDFGenerationError(WarrenBaseError):
    """Raised when WeasyPrint fails to generate the PDF report.

    Mapped to HTTP 500 Internal Server Error.
    """
