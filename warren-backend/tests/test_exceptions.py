"""Tests for app/exceptions.py custom exception hierarchy."""

import pytest


class TestWarrenExceptions:
    """Tests for the Warren exception hierarchy."""

    def test_ticker_not_found_stores_ticker(self) -> None:
        """TickerNotFoundError stores the ticker attribute."""
        from app.exceptions import TickerNotFoundError

        exc = TickerNotFoundError("XXXX4")
        assert exc.ticker == "XXXX4"

    def test_ticker_not_found_str_includes_ticker(self) -> None:
        """str(TickerNotFoundError) includes the ticker symbol."""
        from app.exceptions import TickerNotFoundError

        exc = TickerNotFoundError("PETR4")
        assert "PETR4" in str(exc)

    def test_ticker_not_found_is_warren_base_error(self) -> None:
        """TickerNotFoundError is a subclass of WarrenBaseError."""
        from app.exceptions import TickerNotFoundError, WarrenBaseError

        exc = TickerNotFoundError("WEGE3")
        assert isinstance(exc, WarrenBaseError)

    def test_openai_unavailable_error_is_warren_base_error(self) -> None:
        """OpenAIUnavailableError is a subclass of WarrenBaseError."""
        from app.exceptions import OpenAIUnavailableError, WarrenBaseError

        exc = OpenAIUnavailableError("OpenAI is down")
        assert isinstance(exc, WarrenBaseError)

    def test_rag_empty_result_error_is_warren_base_error(self) -> None:
        """RAGEmptyResultError is a subclass of WarrenBaseError."""
        from app.exceptions import RAGEmptyResultError, WarrenBaseError

        exc = RAGEmptyResultError()
        assert isinstance(exc, WarrenBaseError)

    def test_pdf_generation_error_is_warren_base_error(self) -> None:
        """PDFGenerationError is a subclass of WarrenBaseError."""
        from app.exceptions import PDFGenerationError, WarrenBaseError

        exc = PDFGenerationError("WeasyPrint failed")
        assert isinstance(exc, WarrenBaseError)

    def test_all_exceptions_are_exception_subclasses(self) -> None:
        """All Warren exceptions inherit from Python's Exception."""
        from app.exceptions import (
            OpenAIUnavailableError,
            PDFGenerationError,
            RAGEmptyResultError,
            TickerNotFoundError,
            WarrenBaseError,
        )

        for exc_class in [
            WarrenBaseError,
            TickerNotFoundError,
            OpenAIUnavailableError,
            RAGEmptyResultError,
            PDFGenerationError,
        ]:
            assert issubclass(exc_class, Exception)

    def test_ticker_not_found_can_be_raised_and_caught(self) -> None:
        """TickerNotFoundError can be raised and caught by WarrenBaseError."""
        from app.exceptions import TickerNotFoundError, WarrenBaseError

        with pytest.raises(WarrenBaseError):
            raise TickerNotFoundError("VALE3")

    def test_ticker_not_found_message_format(self) -> None:
        """TickerNotFoundError message contains 'not found in database'."""
        from app.exceptions import TickerNotFoundError

        exc = TickerNotFoundError("ITUB4")
        assert "not found" in str(exc).lower()
