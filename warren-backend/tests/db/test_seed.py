"""Tests for starter database seed data."""
from __future__ import annotations

from sqlalchemy import func, select


class TestSeedDatabase:
    """Starter seed must be deterministic and safe to rerun."""

    async def test_seed_database_inserts_starter_companies_and_financials(
        self, db_session
    ) -> None:
        """Seed inserts the minimum data needed for local smoke tests."""
        from app.db.seed import seed_database
        from app.models.company import Company
        from app.models.financial import Financial

        result = await seed_database(db_session)

        assert result.companies_created == 4
        assert result.financials_created == 3

        companies = (
            await db_session.execute(select(Company).order_by(Company.ticker))
        ).scalars().all()
        assert [company.ticker for company in companies] == [
            "MXRF11",
            "PETR4",
            "TESOURO",
            "WEGE3",
        ]

        financial_years = (
            await db_session.execute(select(Financial.year).order_by(Financial.year))
        ).scalars().all()
        assert financial_years == [2024, 2024, 2024]

    async def test_seed_database_is_idempotent(self, db_session) -> None:
        """Running the seed twice updates existing rows instead of duplicating."""
        from app.db.seed import seed_database
        from app.models.company import Company
        from app.models.financial import Financial

        first = await seed_database(db_session)
        second = await seed_database(db_session)

        assert first.companies_created == 4
        assert second.companies_created == 0
        assert second.companies_updated == 4
        assert second.financials_created == 0
        assert second.financials_updated == 3

        company_count = await db_session.scalar(select(func.count()).select_from(Company))
        financial_count = await db_session.scalar(select(func.count()).select_from(Financial))
        assert company_count == 4
        assert financial_count == 3
