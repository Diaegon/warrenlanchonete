"""ChromaDB client singleton and collection accessor for Warren Lanchonete.

Provides:
    get_chroma_client: Returns the module-level PersistentClient singleton.
    get_collection: Returns the 'buffett_letters' ChromaDB collection.

The PersistentClient is initialized lazily on first call and reused for the
lifetime of the process. In production, the lifespan manager in app/main.py
calls get_chroma_client() at startup to warm the singleton.

Note on embedding functions:
    ChromaDB uses its own embedding function protocol, not LangChain's.
    For production RAG retrieval, use LangChain's Chroma wrapper (which accepts
    OpenAIEmbeddings directly). This module provides the raw PersistentClient
    singleton that is passed to the LangChain Chroma wrapper in RAGService.
"""

from __future__ import annotations

import chromadb

from app.config import settings

# Module-level singleton — initialized lazily on first call to get_chroma_client()
_chroma_client: chromadb.PersistentClient | None = None


def get_chroma_client() -> chromadb.PersistentClient:
    """Return the module-level ChromaDB PersistentClient singleton.

    Creates the client on first call using settings.CHROMA_PERSIST_DIR as the
    persistence path. Subsequent calls return the same instance.

    Returns:
        chromadb.PersistentClient: The singleton ChromaDB client.
    """
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _chroma_client


def get_collection() -> chromadb.Collection:
    """Return the 'buffett_letters' ChromaDB collection.

    Uses get_or_create_collection so the call is idempotent — safe to call
    multiple times or at startup without risking a duplicate collection error.

    The collection uses the default distance metric (cosine).
    Embedding is handled by the LangChain Chroma wrapper in RAGService, not here.

    Returns:
        chromadb.Collection: The 'buffett_letters' collection.
    """
    client = get_chroma_client()
    return client.get_or_create_collection(name="buffett_letters")
