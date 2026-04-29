"""Tests for fundamentals CSV import."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select


HEADER = (
    "ticker,year,roe,lucro_liquido,margem_liquida,receita_liquida,"
    "divida_liquida,ebitda,divida_ebitda,market_cap,p_l,cagr_lucro"
)


async def _seed_company(db_session, ticker: str = "WEGE3") -> None:
    from app.models.company import Company

    db_session.add(
        Company(
            ticker=ticker,
            name=f"{ticker} Test Company",
            sector="Industrial",
            segment="Machines",
            asset_type="STOCK",
        )
    )
    await db_session.commit()


class TestImportFundamentalsCsv:
    """Fundamentals import must be deterministic and idempotent."""

    async def test_import_creates_financials(self, db_session, tmp_path) -> None:
        """Importer creates a financial row for an existing company."""
        await _seed_company(db_session, "WEGE3")
        csv_path = tmp_path / "fundamentals.csv"
        csv_path.write_text(
            "\n".join(
                [
                    HEADER,
                    "WEGE3,2024,28.5,5789000000,15.2,38090000000,1500000000,7600000000,0.4,158000000000,27.3,18.3",
                ]
            ),
            encoding="utf-8",
        )

        from app.db.import_fundamentals import import_fundamentals_csv
        from app.models.financial import Financial

        result = await import_fundamentals_csv(db_session, csv_path)

        assert result.rows_read == 1
        assert result.financials_created == 1
        assert result.financials_updated == 0
        assert result.rows_skipped == 0

        financial = await db_session.scalar(select(Financial))
        assert financial is not None
        assert financial.year == 2024
        assert financial.roe == Decimal("28.5000")
        assert financial.lucro_liquido == Decimal("5789000000.00")
        assert financial.divida_ebitda == Decimal("0.4000")

    async def test_import_updates_existing_financials(self, db_session, tmp_path) -> None:
        """Importer updates the same ticker/year instead of duplicating rows."""
        await _seed_company(db_session, "WEGE3")
        csv_path = tmp_path / "fundamentals.csv"
        csv_path.write_text(
            "\n".join(
                [
                    HEADER,
                    "WEGE3,2024,28.5,5789000000,15.2,38090000000,1500000000,7600000000,0.4,158000000000,27.3,18.3",
                ]
            ),
            encoding="utf-8",
        )

        from app.db.import_fundamentals import import_fundamentals_csv
        from app.models.financial import Financial

        first = await import_fundamentals_csv(db_session, csv_path)
        csv_path.write_text(
            "\n".join(
                [
                    HEADER,
                    "WEGE3,2024,31.1,6200000000,16.0,39000000000,1200000000,8000000000,0.2,170000000000,25.0,19.0",
                ]
            ),
            encoding="utf-8",
        )
        second = await import_fundamentals_csv(db_session, csv_path)

        financials = (await db_session.execute(select(Financial))).scalars().all()
        assert first.financials_created == 1
        assert second.financials_created == 0
        assert second.financials_updated == 1
        assert len(financials) == 1
        assert financials[0].roe == Decimal("31.1000")
        assert financials[0].market_cap == Decimal("170000000000.00")

    async def test_import_keeps_empty_numeric_cells_as_null(self, db_session, tmp_path) -> None:
        """Empty numeric cells import as NULL so partial data can be loaded."""
        await _seed_company(db_session, "PETR4")
        csv_path = tmp_path / "fundamentals.csv"
        csv_path.write_text(
            "\n".join(
                [
                    HEADER,
                    "PETR4,2024,22.1,36700000000,12.5,490000000000,247000000000,274000000000,1.8,498000000000,7.2,",
                ]
            ),
            encoding="utf-8",
        )

        from app.db.import_fundamentals import import_fundamentals_csv
        from app.models.financial import Financial

        result = await import_fundamentals_csv(db_session, csv_path)

        financial = await db_session.scalar(select(Financial))
        assert result.financials_created == 1
        assert financial is not None
        assert financial.cagr_lucro is None

    async def test_import_skips_unknown_ticker(self, db_session, tmp_path) -> None:
        """Fundamentals do not create companies implicitly."""
        csv_path = tmp_path / "fundamentals.csv"
        csv_path.write_text(
            "\n".join(
                [
                    HEADER,
                    "UNKNOWN3,2024,10,100,5,200,10,50,0.2,1000,10,3",
                ]
            ),
            encoding="utf-8",
        )

        from app.db.import_fundamentals import import_fundamentals_csv
        from app.models.financial import Financial

        result = await import_fundamentals_csv(db_session, csv_path)
        count = len((await db_session.execute(select(Financial))).scalars().all())

        assert result.rows_read == 1
        assert result.rows_skipped == 1
        assert count == 0

    async def test_import_skips_invalid_numeric_row(self, db_session, tmp_path) -> None:
        """Bad numeric values are skipped without aborting the full import."""
        await _seed_company(db_session, "WEGE3")
        csv_path = tmp_path / "fundamentals.csv"
        csv_path.write_text(
            "\n".join(
                [
                    HEADER,
                    "WEGE3,2024,not-a-number,5789000000,15.2,38090000000,1500000000,7600000000,0.4,158000000000,27.3,18.3",
                    "WEGE3,2023,25.0,5000000000,14.0,35000000000,1500000000,7000000000,0.5,140000000000,24.0,17.0",
                ]
            ),
            encoding="utf-8",
        )

        from app.db.import_fundamentals import import_fundamentals_csv
        from app.models.financial import Financial

        result = await import_fundamentals_csv(db_session, csv_path)
        financials = (await db_session.execute(select(Financial))).scalars().all()

        assert result.rows_read == 2
        assert result.rows_skipped == 1
        assert result.financials_created == 1
        assert financials[0].year == 2023

    async def test_import_missing_file_can_be_allowed(self, db_session, tmp_path) -> None:
        """Docker startup can skip the import before a fundamentals file exists."""
        from app.db.import_fundamentals import import_fundamentals_csv

        result = await import_fundamentals_csv(
            db_session,
            tmp_path / "missing.csv",
            allow_missing=True,
        )

        assert result.rows_read == 0
        assert result.financials_created == 0

    async def test_import_missing_file_raises_by_default(self, db_session, tmp_path) -> None:
        """Manual imports should fail clearly when the CSV path is wrong."""
        from app.db.import_fundamentals import import_fundamentals_csv

        with pytest.raises(FileNotFoundError):
            await import_fundamentals_csv(db_session, tmp_path / "missing.csv")
