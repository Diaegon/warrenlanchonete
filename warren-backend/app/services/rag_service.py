"""RAG retrieval service for Warren Lanchonete backend.

RAGService wraps a ChromaDB client via LangChain's Chroma wrapper and
exposes a single public method: retrieve(). It builds a semantic query
from the company's financial profile and retrieves relevant passages from
Buffett's shareholder letters.

Query construction strategy (from ARCHITECTURE.md §3):
    - debt_level: maps divida_ebitda to "low debt" / "moderate debt" / "high debt"
    - moat_hint: maps sector to a Buffett-relevant moat description
    - Final query: "Brazilian {sector} company, ROE {roe:.0f}%, {debt_level}, {moat_hint}"

Errors are caught and logged; the method returns [] so the analysis pipeline
can continue with empty citations (graceful degradation).
"""
from __future__ import annotations

import structlog
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

from app.config import settings
from app.metrics import rag_results_count
from app.schemas.portfolio import BuffettCitation

logger = structlog.get_logger(__name__)

# Sector → Buffett-style moat hint for query enrichment
SECTOR_MOAT_HINTS: dict[str, str] = {
    "Industrial": "durable competitive advantage, pricing power",
    "Financeiro": "return on equity, capital allocation",
    "Energia": "commodity exposure, capital intensity",
    "Consumo": "brand moat, consumer loyalty",
    "Tecnologia": "switching costs, scalability",
}


class RAGService:
    """Wraps ChromaDB retrieval for Buffett shareholder letter passages.

    Args:
        chroma_client: A ChromaDB client (PersistentClient or EphemeralClient).
            The LangChain Chroma wrapper handles collection access internally.
    """

    def __init__(self, chroma_client) -> None:
        self._chroma_client = chroma_client
        self._vectorstore = Chroma(
            client=chroma_client,
            collection_name="buffett_letters",
            embedding_function=OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL if settings is not None else "text-embedding-3-small"
            ),
        )

    def retrieve(
        self,
        ticker: str,
        sector: str,
        roe: float,
        divida_ebitda: float,
    ) -> list[BuffettCitation]:
        """Retrieve relevant Buffett passages for a company's financial profile.

        Builds a semantic query from the financial parameters and performs
        a similarity search against the 'buffett_letters' ChromaDB collection.

        Args:
            ticker: B3 ticker symbol (used for logging only).
            sector: B3 sector classification (e.g. 'Industrial', 'Energia').
            roe: Return on equity as a percentage float.
            divida_ebitda: Net debt / EBITDA ratio.

        Returns:
            List of BuffettCitation objects, empty if no results or on error.
        """
        debt_level = (
            "low debt" if divida_ebitda < 1.0
            else "moderate debt" if divida_ebitda < 3.0
            else "high debt"
        )
        moat_hint = SECTOR_MOAT_HINTS.get(sector, "competitive position")
        query = f"Brazilian {sector} company, ROE {roe:.0f}%, {debt_level}, {moat_hint}"

        logger.info("rag.retrieve.started", ticker=ticker, query=query)

        try:
            k = settings.RAG_TOP_K if settings is not None else 3
            docs = self._vectorstore.similarity_search(query, k=k)
            citations = [
                BuffettCitation(
                    year=doc.metadata["year"],
                    passage=doc.page_content,
                    relevance="",  # Filled in by GPT-4o in AnalysisService
                )
                for doc in docs
            ]
            rag_results_count.observe(len(citations))
            logger.info("rag.retrieve.completed", ticker=ticker, results=len(citations))
            return citations

        except Exception as exc:
            logger.error("rag.retrieve.failed", ticker=ticker, error=str(exc))
            return []
