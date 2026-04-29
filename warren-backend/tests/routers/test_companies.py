"""Tests for app/routers/companies.py.

TDD: tests use in-memory SQLite via db_session fixture.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient


async def _seed_companies(db_session) -> None:
    """Seed test database with 2 companies and financial records."""
    from app.models.company import Company
    from app.models.financial import Financial

    wege = Company(
        ticker="WEGE3",
        name="WEG S.A.",
        sector="Industrial",
        segment="Máquinas e Equipamentos",
        asset_type="STOCK",
    )
    petr = Company(
        ticker="PETR4",
        name="Petrobras S.A.",
        sector="Energia",
        segment="Petróleo e Gás",
        asset_type="STOCK",
    )
    db_session.add(wege)
    db_session.add(petr)
    await db_session.flush()

    wege_fin = Financial(
        company_id=wege.id,
        year=2024,
        roe=Decimal("28.5"),
        margem_liquida=Decimal("15.2"),
        cagr_lucro=Decimal("18.3"),
        divida_ebitda=Decimal("0.4"),
    )
    petr_fin = Financial(
        company_id=petr.id,
        year=2024,
        roe=Decimal("22.1"),
        margem_liquida=Decimal("12.5"),
        cagr_lucro=None,
        divida_ebitda=Decimal("1.8"),
    )
    db_session.add(wege_fin)
    db_session.add(petr_fin)
    await db_session.commit()


class TestGetCompanies:
    """Tests for GET /api/companies."""

    async def test_get_companies_returns_all(
        self, async_client: AsyncClient, db_session
    ) -> None:
        """GET /api/companies returns all companies."""
        await _seed_companies(db_session)
        response = await async_client.get("/api/companies")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        tickers = [c["ticker"] for c in data]
        assert "WEGE3" in tickers
        assert "PETR4" in tickers

    async def test_get_companies_empty_database(
        self, async_client: AsyncClient
    ) -> None:
        """GET /api/companies returns empty list when no companies exist."""
        response = await async_client.get("/api/companies")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_get_companies_returns_correct_schema(
        self, async_client: AsyncClient, db_session
    ) -> None:
        """GET /api/companies returns correct schema fields."""
        await _seed_companies(db_session)
        response = await async_client.get("/api/companies")
        data = response.json()
        company = next(c for c in data if c["ticker"] == "WEGE3")
        assert company["name"] == "WEG S.A."
        assert company["sector"] == "Industrial"
        assert company["asset_type"] == "STOCK"

    async def test_get_companies_ordered_by_ticker(
        self, async_client: AsyncClient, db_session
    ) -> None:
        """GET /api/companies returns companies ordered by ticker."""
        await _seed_companies(db_session)
        response = await async_client.get("/api/companies")
        data = response.json()
        tickers = [c["ticker"] for c in data]
        assert tickers == sorted(tickers)


class TestGetCompanyByTicker:
    """Tests for GET /api/companies/{ticker}."""

    async def test_get_company_by_ticker_returns_detail(
        self, async_client: AsyncClient, db_session
    ) -> None:
        """GET /api/companies/{ticker} returns company with financials."""
        await _seed_companies(db_session)
        response = await async_client.get("/api/companies/WEGE3")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "WEGE3"
        assert data["name"] == "WEG S.A."
        assert "financials" in data
        assert len(data["financials"]) == 1
        assert data["financials"][0]["year"] == 2024
        assert data["financials"][0]["roe"] == pytest.approx(28.5)

    async def test_get_company_by_ticker_unknown_returns_404(
        self, async_client: AsyncClient
    ) -> None:
        """GET /api/companies/UNKNOWN returns 404."""
        response = await async_client.get("/api/companies/UNKNOWN1")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    async def test_get_company_null_financials_handled(
        self, async_client: AsyncClient, db_session
    ) -> None:
        """GET /api/companies/{ticker} handles None financial values."""
        await _seed_companies(db_session)
        response = await async_client.get("/api/companies/PETR4")
        assert response.status_code == 200
        data = response.json()
        fin = data["financials"][0]
        assert fin["cagr_lucro"] is None  # Was set to None in seeding
