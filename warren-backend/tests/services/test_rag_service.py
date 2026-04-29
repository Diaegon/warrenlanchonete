"""TDD tests for app/services/rag_service.py — RAGService.

Tests:
    - Returns list[BuffettCitation] for valid query when data is seeded
    - Returns [] when collection is empty
    - Returns [] (and logs error) when the vectorstore raises
    - Query string built correctly for each debt level and sector
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from app.schemas.portfolio import BuffettCitation


class TestRAGServiceRetrieve:
    """Tests for RAGService.retrieve()."""

    async def test_returns_citations_when_data_seeded(self, chroma_with_data):
        """Returns list[BuffettCitation] with length > 0 when collection has data."""
        from app.services.rag_service import RAGService

        # Mock the vectorstore to avoid real OpenAI embedding calls
        with (
            patch("app.services.rag_service.Chroma") as mock_chroma_cls,
            patch("app.services.rag_service.OpenAIEmbeddings"),
        ):
            mock_vectorstore = MagicMock()
            mock_doc1 = MagicMock()
            mock_doc1.page_content = (
                "A truly wonderful business earns very high returns."
            )
            mock_doc1.metadata = {
                "year": 1992,
                "letter_type": "shareholder_letter",
                "topic": "",
                "source_file": "1992_letter.pdf",
            }

            mock_doc2 = MagicMock()
            mock_doc2.page_content = "Price is what you pay. Value is what you get."
            mock_doc2.metadata = {
                "year": 2000,
                "letter_type": "shareholder_letter",
                "topic": "",
                "source_file": "2000_letter.pdf",
            }

            mock_vectorstore.similarity_search.return_value = [mock_doc1, mock_doc2]
            mock_chroma_cls.return_value = mock_vectorstore

            svc = RAGService(chroma_client=chroma_with_data)
            citations = await svc.retrieve(
                ticker="WEGE3",
                sector="Industrial",
                roe=28.5,
                divida_ebitda=0.4,
            )

        assert isinstance(citations, list)
        assert len(citations) > 0
        for c in citations:
            assert isinstance(c, BuffettCitation)
            assert isinstance(c.year, int)
            assert isinstance(c.passage, str)
            assert isinstance(c.relevance, str)

    async def test_returns_empty_list_when_collection_empty(self, chroma_client):
        """Returns [] when the vectorstore similarity_search returns empty."""
        from app.services.rag_service import RAGService

        with (
            patch("app.services.rag_service.Chroma") as mock_chroma_cls,
            patch("app.services.rag_service.OpenAIEmbeddings"),
        ):
            mock_vectorstore = MagicMock()
            mock_vectorstore.similarity_search.return_value = []
            mock_chroma_cls.return_value = mock_vectorstore

            svc = RAGService(chroma_client=chroma_client)
            citations = await svc.retrieve(
                ticker="PETR4",
                sector="Energia",
                roe=10.0,
                divida_ebitda=2.5,
            )

        assert citations == []

    async def test_returns_empty_list_when_vectorstore_raises(self, chroma_client):
        """Returns [] and logs error when vectorstore raises an exception."""
        from app.services.rag_service import RAGService

        with (
            patch("app.services.rag_service.Chroma") as mock_chroma_cls,
            patch("app.services.rag_service.OpenAIEmbeddings"),
        ):
            mock_vectorstore = MagicMock()
            mock_vectorstore.similarity_search.side_effect = RuntimeError(
                "ChromaDB unavailable"
            )
            mock_chroma_cls.return_value = mock_vectorstore

            svc = RAGService(chroma_client=chroma_client)
            citations = await svc.retrieve(
                ticker="VALE3",
                sector="Energia",
                roe=15.0,
                divida_ebitda=1.5,
            )

        assert citations == []


class TestRAGServiceMalformedMetadata:
    """Tests for RAGService.retrieve() with malformed ChromaDB metadata."""

    async def test_missing_year_key_returns_citation_with_zero(self, chroma_client):
        """Documents without a 'year' key in metadata return citation with year=0."""
        from app.services.rag_service import RAGService

        with (
            patch("app.services.rag_service.Chroma") as mock_chroma_cls,
            patch("app.services.rag_service.OpenAIEmbeddings"),
        ):
            mock_vectorstore = MagicMock()
            mock_doc = MagicMock()
            mock_doc.page_content = "Price is what you pay."
            # No 'year' key in metadata
            mock_doc.metadata = {
                "letter_type": "shareholder_letter",
                "source_file": "unknown.pdf",
            }
            mock_vectorstore.similarity_search.return_value = [mock_doc]
            mock_chroma_cls.return_value = mock_vectorstore

            svc = RAGService(chroma_client=chroma_client)
            citations = await svc.retrieve(
                ticker="WEGE3", sector="Industrial", roe=25.0, divida_ebitda=0.5
            )

        assert len(citations) == 1
        assert citations[0].year == 0  # default when year key is missing

    async def test_missing_year_key_does_not_swallow_all_results(self, chroma_client):
        """A doc without 'year' does not discard valid docs with 'year'."""
        from app.services.rag_service import RAGService

        with (
            patch("app.services.rag_service.Chroma") as mock_chroma_cls,
            patch("app.services.rag_service.OpenAIEmbeddings"),
        ):
            mock_vectorstore = MagicMock()
            good_doc = MagicMock()
            good_doc.page_content = "Wonderful businesses."
            good_doc.metadata = {
                "year": 1992,
                "letter_type": "shareholder_letter",
                "source_file": "1992_letter.pdf",
            }

            bad_doc = MagicMock()
            bad_doc.page_content = "Malformed document."
            bad_doc.metadata = {}  # no year

            mock_vectorstore.similarity_search.return_value = [good_doc, bad_doc]
            mock_chroma_cls.return_value = mock_vectorstore

            svc = RAGService(chroma_client=chroma_client)
            citations = await svc.retrieve(
                ticker="PETR4", sector="Energia", roe=12.0, divida_ebitda=3.0
            )

        assert len(citations) == 2
        assert citations[0].year == 1992
        assert citations[1].year == 0


class TestRAGServiceQueryConstruction:
    """Tests for query string construction in RAGService.retrieve()."""

    async def _get_query_string(
        self, chroma_client, ticker, sector, roe, divida_ebitda
    ):
        """Helper: run retrieve() and capture the query passed to similarity_search."""
        from app.services.rag_service import RAGService

        with (
            patch("app.services.rag_service.Chroma") as mock_chroma_cls,
            patch("app.services.rag_service.OpenAIEmbeddings"),
        ):
            mock_vectorstore = MagicMock()
            mock_vectorstore.similarity_search.return_value = []
            mock_chroma_cls.return_value = mock_vectorstore

            svc = RAGService(chroma_client=chroma_client)
            await svc.retrieve(
                ticker=ticker, sector=sector, roe=roe, divida_ebitda=divida_ebitda
            )

            call_args = mock_vectorstore.similarity_search.call_args
            return call_args[0][0]  # First positional arg is the query string

    async def test_query_contains_low_debt_when_divida_ebitda_below_1(
        self, chroma_client
    ):
        """divida_ebitda < 1.0 → 'low debt' in query."""
        query = await self._get_query_string(
            chroma_client, "WEGE3", "Industrial", 25.0, 0.4
        )
        assert "low debt" in query

    async def test_query_contains_moderate_debt_when_divida_ebitda_1_to_3(
        self, chroma_client
    ):
        """1.0 <= divida_ebitda < 3.0 → 'moderate debt' in query."""
        query = await self._get_query_string(
            chroma_client, "ITUB4", "Financeiro", 18.0, 2.0
        )
        assert "moderate debt" in query

    async def test_query_contains_high_debt_when_divida_ebitda_above_3(
        self, chroma_client
    ):
        """divida_ebitda >= 3.0 → 'high debt' in query."""
        query = await self._get_query_string(
            chroma_client, "PETR4", "Energia", 12.0, 4.5
        )
        assert "high debt" in query

    async def test_query_uses_sector_moat_hint_for_known_sector(self, chroma_client):
        """Known sectors map to their specific moat hints."""
        query = await self._get_query_string(
            chroma_client, "WEGE3", "Industrial", 25.0, 0.4
        )
        assert "durable competitive advantage" in query

    async def test_query_uses_default_hint_for_unknown_sector(self, chroma_client):
        """Unknown sector falls back to 'competitive position'."""
        query = await self._get_query_string(
            chroma_client, "XPTO3", "Unknown Sector XYZ", 10.0, 1.5
        )
        assert "competitive position" in query

    async def test_query_includes_sector_and_roe(self, chroma_client):
        """Query string includes sector name and ROE value."""
        query = await self._get_query_string(
            chroma_client, "MGLU3", "Consumo", 8.0, 1.8
        )
        assert "Consumo" in query
        assert "8%" in query or "8.0%" in query or "8" in query
