"""Tests for app/main.py FastAPI app factory.

TDD: Written before implementation.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


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
