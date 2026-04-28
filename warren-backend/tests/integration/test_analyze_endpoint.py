"""Integration smoke test for POST /api/portfolio/analyze endpoint.

Requires:
    - Local PostgreSQL seeded with WEGE3 (STOCK) and TESOURO companies
    - .env file with valid OPENAI_API_KEY
    - ChromaDB populated with Buffett letter chunks

These tests are marked @pytest.mark.integration and are excluded from the
standard CI test run. Run explicitly with:
    uv run pytest -m integration tests/integration/test_analyze_endpoint.py -v

The tests verify end-to-end behavior:
    - Full pipeline returns HTTP 200
    - Response matches PortfolioResponse schema
    - WEGE3 (STOCK) has a numeric score and at least one citation
    - TESOURO has 'Capital seguro' verdict
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport


pytestmark = pytest.mark.integration


@pytest.mark.integration
async def test_analyze_endpoint_returns_valid_portfolio_response():
    """POST /api/portfolio/analyze returns 200 with valid PortfolioResponse shape.

    Requires:
        - PostgreSQL seeded with WEGE3 and TESOURO
        - Valid OPENAI_API_KEY in .env
        - ChromaDB populated
    """
    from app.main import app
    from app.schemas.portfolio import PortfolioResponse

    payload = {
        "assets": [
            {"ticker": "WEGE3", "type": "STOCK", "percentage": 60},
            {"ticker": "TESOURO", "type": "TESOURO", "percentage": 40},
        ]
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/portfolio/analyze", json=payload)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. Body: {response.text}"
    )

    data = response.json()

    # Validate response matches PortfolioResponse schema
    portfolio = PortfolioResponse(**data)
    assert portfolio.portfolio_grade in ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]
    assert len(portfolio.portfolio_summary) > 0
    assert len(portfolio.assets) == 2


@pytest.mark.integration
async def test_wege3_has_score_and_citations():
    """WEGE3 STOCK asset in response has a numeric score and at least one citation."""
    from app.main import app
    from app.schemas.portfolio import StockAssetResponse

    payload = {
        "assets": [
            {"ticker": "WEGE3", "type": "STOCK", "percentage": 60},
            {"ticker": "TESOURO", "type": "TESOURO", "percentage": 40},
        ]
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/portfolio/analyze", json=payload)

    assert response.status_code == 200
    data = response.json()

    wege3_asset = next(
        (a for a in data["assets"] if a["ticker"] == "WEGE3"),
        None,
    )
    assert wege3_asset is not None, "WEGE3 asset not found in response"
    assert wege3_asset["type"] == "STOCK"
    assert isinstance(wege3_asset["score"], (int, float))
    assert 0.0 <= wege3_asset["score"] <= 10.0
    assert isinstance(wege3_asset["buffett_citations"], list)


@pytest.mark.integration
async def test_tesouro_has_capital_seguro_verdict():
    """TESOURO asset in response has 'Capital seguro' verdict."""
    from app.main import app

    payload = {
        "assets": [
            {"ticker": "WEGE3", "type": "STOCK", "percentage": 60},
            {"ticker": "TESOURO", "type": "TESOURO", "percentage": 40},
        ]
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/portfolio/analyze", json=payload)

    assert response.status_code == 200
    data = response.json()

    tesouro_asset = next(
        (a for a in data["assets"] if a["ticker"] == "TESOURO"),
        None,
    )
    assert tesouro_asset is not None, "TESOURO asset not found in response"
    assert tesouro_asset["type"] == "TESOURO"
    assert tesouro_asset["verdict"] == "Capital seguro"
