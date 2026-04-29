"""Tests for starter database seed data."""

from __future__ import annotations

from sqlalchemy import func, select


class TestSeedDatabase:
    """Starter seed must be deterministic and safe to rerun."""

    async def test_seed_database_inserts_fallback_companies_and_financials(
        self, db_session, monkeypatch
    ) -> None:
        """Seed inserts fallback data when B3 cache is unavailable."""
        monkeypatch.setenv("B3_TICKERS_CSV", "/tmp/does-not-exist.csv")

        from app.db.seed import seed_database
        from app.models.company import Company
        from app.models.financial import Financial

        result = await seed_database(db_session)

        assert result.companies_created == 4
        assert result.financials_created == 3

        companies = (
            (await db_session.execute(select(Company).order_by(Company.ticker)))
            .scalars()
            .all()
        )
        assert [company.ticker for company in companies] == [
            "MXRF11",
            "PETR4",
            "TESOURO",
            "WEGE3",
        ]

        financial_years = (
            (await db_session.execute(select(Financial.year).order_by(Financial.year)))
            .scalars()
            .all()
        )
        assert financial_years == [2024, 2024, 2024]

    async def test_seed_database_loads_b3_tickers_csv(
        self, db_session, monkeypatch, tmp_path
    ) -> None:
        """Seed loads all available B3 ticker company rows from CSV."""
        csv_path = tmp_path / "tickers.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "ticker,name,cnpj,sector,segment,asset_type,source_url,source_updated_at",
                    "VALE3,VALE S.A.,33592510000154,Materiais Básicos,Minerais Metálicos,STOCK,,",
                    "TUPY3,TUPY S.A.,84683374000300,Bens Industriais,Material Rodoviário,STOCK,,",
                    "SAPR3,CIA SANEAMENTO DO PARANA - SANEPAR,76484013000145,Utilidade Pública,Água e Saneamento,STOCK,,",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("B3_TICKERS_CSV", str(csv_path))

        from app.db.seed import seed_database
        from app.models.company import Company

        result = await seed_database(db_session)

        assert result.companies_created == 7  # 3 CSV rows + 3 fallback rows + TESOURO

        companies = (
            (await db_session.execute(select(Company).order_by(Company.ticker)))
            .scalars()
            .all()
        )
        assert [company.ticker for company in companies] == [
            "MXRF11",
            "PETR4",
            "SAPR3",
            "TESOURO",
            "TUPY3",
            "VALE3",
            "WEGE3",
        ]

    async def test_seed_database_is_idempotent(self, db_session, monkeypatch) -> None:
        """Running the seed twice updates existing rows instead of duplicating."""
        monkeypatch.setenv("B3_TICKERS_CSV", "/tmp/does-not-exist.csv")

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

        company_count = await db_session.scalar(
            select(func.count()).select_from(Company)
        )
        financial_count = await db_session.scalar(
            select(func.count()).select_from(Financial)
        )
        assert company_count == 4
        assert financial_count == 3
