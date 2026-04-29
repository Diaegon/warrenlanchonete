"""TDD tests for app/rag/client.py — ChromaDB singleton and collection accessor.

Tests:
    - get_collection returns a collection named 'buffett_letters'
    - get_collection is idempotent (two calls return same collection)
"""
from __future__ import annotations

from unittest.mock import patch

import chromadb


class TestGetCollection:
    """Tests for get_collection() function."""

    def test_get_collection_returns_buffett_letters_collection(self, chroma_client):
        """get_collection() should return a collection named 'buffett_letters'."""
        with patch("app.rag.client.get_chroma_client", return_value=chroma_client):
            from app.rag.client import get_collection

            collection = get_collection()
            assert collection.name == "buffett_letters"

    def test_get_collection_is_idempotent(self, chroma_client):
        """Calling get_collection() twice returns the same collection (no duplicate error)."""
        with patch("app.rag.client.get_chroma_client", return_value=chroma_client):
            from app.rag.client import get_collection

            col1 = get_collection()
            col2 = get_collection()
            # Both calls should return the same collection name
            assert col1.name == col2.name == "buffett_letters"


class TestGetChromaClient:
    """Tests for get_chroma_client() singleton behavior."""

    def test_get_chroma_client_returns_client(self):
        """get_chroma_client() returns a chromadb client instance."""
        import app.rag.client as client_module

        # Reset singleton so we can test fresh init path
        original = client_module._chroma_client
        client_module._chroma_client = None

        ephemeral = chromadb.EphemeralClient()

        try:
            # Patch both PersistentClient and settings to avoid needing a .env
            with patch("app.rag.client.chromadb.PersistentClient", return_value=ephemeral), \
                 patch("app.rag.client.settings") as mock_settings:
                mock_settings.CHROMA_PERSIST_DIR = "./test_rag_data"
                result = client_module.get_chroma_client()
                assert result is not None
        finally:
            # Restore original singleton state
            client_module._chroma_client = original

    def test_get_chroma_client_singleton_returns_same_instance(self):
        """get_chroma_client() returns the same instance on repeated calls."""
        import app.rag.client as client_module

        original = client_module._chroma_client
        test_client = chromadb.EphemeralClient()
        client_module._chroma_client = test_client

        try:
            from app.rag.client import get_chroma_client

            result1 = get_chroma_client()
            result2 = get_chroma_client()
            assert result1 is result2
            assert result1 is test_client
        finally:
            client_module._chroma_client = original
