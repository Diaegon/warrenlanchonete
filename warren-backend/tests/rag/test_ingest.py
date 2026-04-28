"""TDD tests for app/rag/ingest.py — PDF ingestion CLI.

Tests:
    - Parses year from '1992_letter.pdf' → year=1992
    - Skips non-matching filenames (e.g. 'letter_1992.pdf') with warning
    - Chunks stored with correct metadata
    - Second run on same file is idempotent (count doesn't increase)
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock, patch, call

import chromadb
import pytest


class TestParseYear:
    """Tests for year extraction from PDF and HTML filenames."""

    def test_parse_year_from_letter_pdf(self):
        """Extracts year=1992 from '1992_letter.pdf'."""
        from app.rag.ingest import parse_year_from_filename

        assert parse_year_from_filename("1992_letter.pdf") == 1992

    def test_parse_year_from_bare_pdf(self):
        """Extracts year=2004 from '2004.pdf' (actual naming in buffett_letters/)."""
        from app.rag.ingest import parse_year_from_filename

        assert parse_year_from_filename("2004.pdf") == 2004

    def test_parse_year_from_html(self):
        """Extracts year=1984 from '1984.html'."""
        from app.rag.ingest import parse_year_from_filename

        assert parse_year_from_filename("1984.html") == 1984

    def test_parse_year_from_letter_html(self):
        """Extracts year=1984 from '1984_letter.html'."""
        from app.rag.ingest import parse_year_from_filename

        assert parse_year_from_filename("1984_letter.html") == 1984

    def test_parse_year_returns_none_for_invalid_filename(self):
        """Returns None for 'letter_1992.pdf' (non-matching pattern)."""
        from app.rag.ingest import parse_year_from_filename

        assert parse_year_from_filename("letter_1992.pdf") is None

    def test_parse_year_returns_none_for_generic_name(self):
        """Returns None for filenames without year prefix."""
        from app.rag.ingest import parse_year_from_filename

        assert parse_year_from_filename("buffett_letter.pdf") is None
        assert parse_year_from_filename("1992letter.pdf") is None
        assert parse_year_from_filename("1992_letters.pdf") is None

    def test_parse_year_handles_various_valid_years(self):
        """Parses any 4-digit year from all valid filename patterns."""
        from app.rag.ingest import parse_year_from_filename

        assert parse_year_from_filename("1977_letter.pdf") == 1977
        assert parse_year_from_filename("2023_letter.pdf") == 2023
        assert parse_year_from_filename("2004.pdf") == 2004
        assert parse_year_from_filename("1984.html") == 1984


class TestIngestPDF:
    """Tests for the PDF ingestion pipeline."""

    def _make_mock_fitz_page(self, text: str):
        """Create a mock fitz page that returns given text."""
        page = MagicMock()
        page.get_text.return_value = text
        return page

    def _make_mock_fitz_doc(self, pages_text: list[str]):
        """Create a mock fitz document with given pages."""
        mock_doc = MagicMock()
        mock_pages = [self._make_mock_fitz_page(t) for t in pages_text]
        mock_doc.__iter__ = MagicMock(return_value=iter(mock_pages))
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        return mock_doc

    def test_chunks_stored_with_correct_metadata(self, chroma_client):
        """Chunks ingested from a PDF should have correct metadata fields."""
        from app.rag.ingest import ingest_pdf

        year = 1992
        source_file = "1992_letter.pdf"
        # Long enough text to be chunked (> 100 chars, < 400 chars so no further splitting)
        passage = (
            "A truly wonderful business earns very high returns on the capital "
            "required for its operation. We search for durable competitive advantages "
            "that protect the business from competition. A strong brand or cost advantage "
            "creates a wide moat around the economic castle."
        )
        page_text = passage

        mock_doc = self._make_mock_fitz_doc([page_text])

        with patch("app.rag.ingest.fitz.open", return_value=mock_doc), \
             patch("app.rag.ingest.OpenAIEmbeddings") as mock_embeddings_cls:
            # Mock the embedding function to return fixed vectors
            mock_ef = MagicMock()
            mock_ef.embed_documents.return_value = [[0.1] * 10]
            mock_ef.embed_query.return_value = [0.1] * 10
            mock_embeddings_cls.return_value = mock_ef

            collection = chroma_client.get_or_create_collection("test_metadata_1992")
            ingest_pdf(source_file, year, collection, mock_ef, pdf_path="/fake/path.pdf")

        # Verify at least one document was stored
        results = collection.get(include=["metadatas", "documents"])
        assert len(results["ids"]) > 0

        # Verify metadata fields
        meta = results["metadatas"][0]
        assert meta["year"] == 1992
        assert meta["letter_type"] == "shareholder_letter"
        assert meta["source_file"] == "1992_letter.pdf"
        assert "topic" in meta

    def test_chunk_ids_follow_naming_convention(self, chroma_client):
        """Chunk IDs must follow '{year}_letter_chunk_{index:03d}' convention."""
        from app.rag.ingest import ingest_pdf

        year = 2000
        source_file = "2000_letter.pdf"
        passage = (
            "Price is what you pay. Value is what you get. "
            "This principle is fundamental to successful long-term investing. "
            "Understanding the difference between price and value is what separates "
            "great investors from the rest of the market participants."
        )

        mock_doc = self._make_mock_fitz_doc([passage])
        mock_ef = MagicMock()
        mock_ef.embed_documents.return_value = [[0.2] * 10]
        mock_ef.embed_query.return_value = [0.2] * 10

        # Use a unique collection name to avoid cross-test contamination
        collection = chroma_client.get_or_create_collection("test_chunk_ids_2000")

        with patch("app.rag.ingest.fitz.open", return_value=mock_doc):
            ingest_pdf(source_file, year, collection, mock_ef, pdf_path="/fake/path.pdf")

        results = collection.get(include=["metadatas"])
        # There must be exactly one document from 2000
        assert len(results["ids"]) == 1
        for doc_id in results["ids"]:
            assert re.match(r"^2000_letter_chunk_\d{3}$", doc_id), (
                f"ID '{doc_id}' does not match expected pattern"
            )

    def test_ingestion_is_idempotent(self, chroma_client):
        """Second run on the same file should not increase document count."""
        from app.rag.ingest import ingest_pdf

        year = 1992
        source_file = "1992_letter.pdf"
        passage = (
            "A truly wonderful business earns very high returns on the capital "
            "required for its operation. We search for durable competitive advantages "
            "that protect the business from competition for many years into the future."
        )

        mock_doc = self._make_mock_fitz_doc([passage])
        mock_ef = MagicMock()
        mock_ef.embed_documents.return_value = [[0.1] * 10]
        mock_ef.embed_query.return_value = [0.1] * 10

        collection = chroma_client.get_or_create_collection("test_idempotent_1992")

        with patch("app.rag.ingest.fitz.open", return_value=mock_doc):
            ingest_pdf(source_file, year, collection, mock_ef, pdf_path="/fake/path.pdf")
            count_after_first = collection.count()

            # Reset mock_doc iterator for second call
            mock_doc.__iter__ = MagicMock(
                return_value=iter([self._make_mock_fitz_page(passage)])
            )
            ingest_pdf(source_file, year, collection, mock_ef, pdf_path="/fake/path.pdf")
            count_after_second = collection.count()

        assert count_after_second == count_after_first, (
            f"Second run increased count from {count_after_first} to {count_after_second}"
        )

    def test_short_chunks_filtered_out(self, chroma_client):
        """Chunks shorter than 100 chars should be filtered out."""
        from app.rag.ingest import ingest_pdf

        year = 2007
        source_file = "2007_letter.pdf"
        # Mix of long and short paragraphs
        page_text = (
            "Short.\n\n"
            "Also too short to matter.\n\n"
            "Our favorite holding period is forever. We look for durable competitive advantages "
            "that protect the business from competition. This long-term perspective allows us to "
            "hold great businesses through market downturns without losing sleep at night."
        )

        mock_doc = self._make_mock_fitz_doc([page_text])
        mock_ef = MagicMock()
        mock_ef.embed_documents.return_value = [[0.3] * 10]
        mock_ef.embed_query.return_value = [0.3] * 10

        collection = chroma_client.get_or_create_collection("test_filter_short_2007")

        with patch("app.rag.ingest.fitz.open", return_value=mock_doc):
            ingest_pdf(source_file, year, collection, mock_ef, pdf_path="/fake/path.pdf")

        # Only the long chunk should be stored
        results = collection.get(include=["documents"])
        for doc_text in results["documents"]:
            assert len(doc_text) >= 100, f"Short chunk was not filtered: '{doc_text[:50]}...'"


class TestIngestHTML:
    """Tests for HTML file ingestion."""

    def test_ingest_html_file_stores_chunks(self, chroma_client):
        """HTML files should be ingested using html.parser text extraction."""
        from app.rag.ingest import ingest_pdf
        import tempfile, os

        html_content = """<html><body>
        <p>Our gain in net worth during 1984 was a very meaningful amount of capital.
        We search for durable competitive advantages that protect our businesses from competition
        over many decades. The key is finding businesses with strong economic moats.</p>
        <p>Price is what you pay. Value is what you get. Understanding this distinction
        separates good investors from the rest. We focus on long-term intrinsic value
        rather than short-term price fluctuations in the stock market.</p>
        </body></html>"""

        with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
            f.write(html_content)
            tmp_path = f.name

        try:
            mock_ef = MagicMock()
            # Return one embedding vector per chunk (however many there are)
            mock_ef.embed_documents.side_effect = lambda texts: [[0.1 * i] * 10 for i in range(1, len(texts) + 1)]
            collection = chroma_client.get_or_create_collection("test_html_1984")

            count = ingest_pdf("1984.html", 1984, collection, mock_ef, pdf_path=tmp_path)
            assert count > 0

            results = collection.get(include=["metadatas"])
            assert len(results["ids"]) > 0
            assert results["metadatas"][0]["year"] == 1984
            assert results["metadatas"][0]["source_file"] == "1984.html"
        finally:
            os.unlink(tmp_path)

    def test_ingest_skips_binary_html_files(self, chroma_client):
        """Binary/unreadable HTML files should be skipped with a warning."""
        from app.rag.ingest import ingest_pdf
        import tempfile, os

        # Write binary garbage — simulates the corrupted 1977–1983 files
        binary_content = bytes(range(256)) * 10

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            f.write(binary_content)
            tmp_path = f.name

        try:
            mock_ef = MagicMock()
            collection = chroma_client.get_or_create_collection("test_binary_skip")

            count = ingest_pdf("1985.html", 1985, collection, mock_ef, pdf_path=tmp_path)
            assert count == 0
            assert collection.count() == 0
        finally:
            os.unlink(tmp_path)


class TestRunIngestion:
    """Tests for the main run() entry point that scans the directory."""

    def test_skips_non_matching_filename_with_warning(self, tmp_path):
        """Non-matching filenames should be skipped and a warning logged."""
        from unittest.mock import MagicMock, patch

        # Create a temp dir with a non-matching file
        bad_file = tmp_path / "letter_1992.pdf"
        bad_file.write_bytes(b"fake")

        with patch("app.rag.ingest.get_collection") as mock_get_col, \
             patch("app.rag.ingest.OpenAIEmbeddings"), \
             patch("app.rag.ingest.settings") as mock_settings:

            mock_settings.EMBEDDING_MODEL = "text-embedding-3-small"
            mock_get_col.return_value = MagicMock()

            import structlog.testing
            with structlog.testing.capture_logs() as captured:
                from app.rag.ingest import run
                run(source_dir=tmp_path)

        warning_events = [
            log for log in captured
            if log.get("log_level") == "warning" or "skip" in log.get("event", "").lower()
        ]
        assert len(warning_events) > 0, (
            f"Expected a warning log for non-matching filename. Got: {captured}"
        )
