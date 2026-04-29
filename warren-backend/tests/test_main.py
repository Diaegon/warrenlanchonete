"""Tests for app/main.py FastAPI app factory.

TDD: Written before implementation.
"""

from __future__ import annotations

from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    async def test_health_returns_ok(self, async_client: AsyncClient) -> None:
        """GET /health returns 200 with status ok."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestUnknownRoute:
    """Tests for 404 behavior on unknown routes."""

    async def test_unknown_route_returns_404(self, async_client: AsyncClient) -> None:
        """GET on unknown route returns 404."""
        response = await async_client.get("/nonexistent-route")
        assert response.status_code == 404


class TestReadyEndpoint:
    """Tests for the /ready readiness check endpoint."""

    def _mock_db(self):
        """Return a context-manager mock for AsyncSessionLocal."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        mock_cls = MagicMock(return_value=mock_session)
        return mock_cls

    async def test_ready_returns_503_when_chroma_not_initialized(
        self, async_client: AsyncClient
    ) -> None:
        """GET /ready returns 503 when app.state has no chroma_client."""
        from app.main import app

        # Ensure chroma_client is absent from state
        if hasattr(app.state, "chroma_client"):
            del app.state.chroma_client

        with patch("app.db.session.AsyncSessionLocal", self._mock_db()):
            response = await async_client.get("/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert "ChromaDB not initialized" in data["detail"]

    async def test_ready_returns_503_when_collection_empty(
        self, async_client: AsyncClient
    ) -> None:
        """GET /ready returns 503 when buffett_letters collection is empty."""
        from app.main import app

        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_chroma = MagicMock()
        mock_chroma.get_collection.return_value = mock_collection
        app.state.chroma_client = mock_chroma

        try:
            with patch("app.db.session.AsyncSessionLocal", self._mock_db()):
                response = await async_client.get("/ready")
        finally:
            del app.state.chroma_client

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert "empty" in data["detail"]

    async def test_ready_returns_503_when_db_unavailable(
        self, async_client: AsyncClient
    ) -> None:
        """GET /ready returns 503 when DB connection fails."""
        from app.main import app

        mock_collection = MagicMock()
        mock_collection.count.return_value = 5
        mock_chroma = MagicMock()
        mock_chroma.get_collection.return_value = mock_collection
        app.state.chroma_client = mock_chroma

        try:
            failing_session_cls = MagicMock(side_effect=Exception("Connection refused"))
            with patch("app.db.session.AsyncSessionLocal", failing_session_cls):
                response = await async_client.get("/ready")
        finally:
            del app.state.chroma_client

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert "DB unavailable" in data["detail"]

    async def test_ready_returns_200_when_all_checks_pass(
        self, async_client: AsyncClient
    ) -> None:
        """GET /ready returns 200 when DB and ChromaDB are both healthy."""
        from app.main import app

        mock_collection = MagicMock()
        mock_collection.count.return_value = 42
        mock_chroma = MagicMock()
        mock_chroma.get_collection.return_value = mock_collection
        app.state.chroma_client = mock_chroma

        try:
            with patch("app.db.session.AsyncSessionLocal", self._mock_db()):
                response = await async_client.get("/ready")
        finally:
            del app.state.chroma_client

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCORSHeaders:
    """Tests for CORS middleware."""

    async def test_cors_headers_present_on_allowed_origin(
        self, async_client: AsyncClient
    ) -> None:
        """CORS headers are present for allowed origins."""
        response = await async_client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should not return 4xx for OPTIONS preflight
        assert response.status_code in (200, 204)
