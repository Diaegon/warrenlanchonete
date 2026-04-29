"""Import annual company fundamentals from CSV into the financials table.

Expected CSV columns:
    ticker,year,roe,lucro_liquido,margem_liquida,receita_liquida,
    divida_liquida,ebitda,divida_ebitda,market_cap,p_l,cagr_lucro

Run after companies have been seeded:
    uv run python -m app.db.import_fundamentals --path ../warren-ingestion/data/processed/fundamentals.csv
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import structlog
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import _make_async_url
from app.models.company import Company
from app.models.financial import Financial

logger = structlog.get_logger(__name__)

DEV_DATABASE_URL = "postgresql://warren:password@localhost:5432/warren"
DEFAULT_FUNDAMENTALS_CSV = Path("../warren-ingestion/data/processed/fundamentals.csv")

REQUIRED_COLUMNS = ("ticker", "year")
NUMERIC_COLUMNS = (
    "roe",
    "lucro_liquido",
    "margem_liquida",
    "receita_liquida",
    "divida_liquida",
    "ebitda",
    "divida_ebitda",
    "market_cap",
    "p_l",
    "cagr_lucro",
)
EXPECTED_COLUMNS = REQUIRED_COLUMNS + NUMERIC_COLUMNS


@dataclass(frozen=True)
class FundamentalsImportResult:
    """Counts produced by a fundamentals import run."""

    rows_read: int = 0
    financials_created: int = 0
    financials_updated: int = 0
    rows_skipped: int = 0


def _empty_to_none(value: str | None) -> str | None:
    """Normalize empty CSV cells to None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_decimal(value: str | None, *, row_number: int, column: str) -> Decimal | None:
    """Parse a nullable decimal CSV cell."""
    normalized = _empty_to_none(value)
    if normalized is None:
        return None
    try:
        return Decimal(normalized.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"row {row_number}: invalid decimal for {column}: {value!r}") from exc


def _parse_year(value: str | None, *, row_number: int) -> int:
    """Parse a required fiscal year."""
    normalized = _empty_to_none(value)
    if normalized is None:
        raise ValueError(f"row {row_number}: year is required")
    try:
        year = int(normalized)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: invalid year: {value!r}") from exc
    if year < 1900 or year > 2100:
        raise ValueError(f"row {row_number}: year out of supported range: {year}")
    return year


def _validate_header(fieldnames: list[str] | None) -> None:
    """Ensure the CSV includes all columns used by the importer."""
    if fieldnames is None:
        raise ValueError("fundamentals CSV is empty")
    missing = [column for column in EXPECTED_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"fundamentals CSV missing columns: {', '.join(missing)}")


def _row_values(row: dict[str, str], *, row_number: int) -> tuple[str, int, dict[str, Decimal | int | None]]:
    """Convert a CSV row into ticker, year, and Financial values."""
    ticker = (_empty_to_none(row.get("ticker")) or "").upper()
    if not ticker:
        raise ValueError(f"row {row_number}: ticker is required")

    year = _parse_year(row.get("year"), row_number=row_number)
    values: dict[str, Decimal | int | None] = {"year": year}
    for column in NUMERIC_COLUMNS:
        values[column] = _parse_decimal(row.get(column), row_number=row_number, column=column)

    return ticker, year, values


async def import_fundamentals_csv(
    session: AsyncSession,
    csv_path: Path,
    *,
    allow_missing: bool = False,
) -> FundamentalsImportResult:
    """Upsert annual fundamentals from CSV into the database.

    Args:
        session: Open SQLAlchemy async session.
        csv_path: CSV path with the expected fundamentals columns.
        allow_missing: Return an empty result when csv_path does not exist.

    Returns:
        Counts for read, created, updated, and skipped rows.
    """
    if not csv_path.exists():
        if allow_missing:
            logger.warning("fundamentals.import.file_missing", path=str(csv_path))
            return FundamentalsImportResult()
        raise FileNotFoundError(f"fundamentals CSV not found: {csv_path}")

    rows_read = 0
    financials_created = 0
    financials_updated = 0
    rows_skipped = 0

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        _validate_header(reader.fieldnames)

        for row_number, row in enumerate(reader, start=2):
            rows_read += 1
            try:
                ticker, year, values = _row_values(row, row_number=row_number)
            except ValueError as exc:
                rows_skipped += 1
                logger.warning("fundamentals.import.row_invalid", error=str(exc), row_number=row_number)
                continue

            company = await session.scalar(select(Company).where(Company.ticker == ticker))
            if company is None:
                rows_skipped += 1
                logger.warning(
                    "fundamentals.import.company_missing",
                    ticker=ticker,
                    row_number=row_number,
                )
                continue

            financial = await session.scalar(
                select(Financial).where(
                    Financial.company_id == company.id,
                    Financial.year == year,
                )
            )
            if financial is None:
                session.add(Financial(company_id=company.id, **values))
                financials_created += 1
            else:
                for field, value in values.items():
                    setattr(financial, field, value)
                financials_updated += 1

    await session.commit()

    return FundamentalsImportResult(
        rows_read=rows_read,
        financials_created=financials_created,
        financials_updated=financials_updated,
        rows_skipped=rows_skipped,
    )


def _resolve_csv_path(path: str | None) -> Path:
    """Resolve the CLI/env CSV path."""
    if path:
        return Path(path)
    return Path(os.environ.get("FUNDAMENTALS_CSV", DEFAULT_FUNDAMENTALS_CSV))


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Import Warren fundamentals CSV into the DB.")
    parser.add_argument("--path", help="Path to fundamentals.csv")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Exit successfully when the CSV file is not present.",
    )
    return parser.parse_args()


async def main() -> None:
    """Import the configured fundamentals CSV."""
    load_dotenv()
    args = _parse_args()
    csv_path = _resolve_csv_path(args.path)
    database_url = os.environ.get("DATABASE_URL", DEV_DATABASE_URL)
    engine = create_async_engine(_make_async_url(database_url), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        result = await import_fundamentals_csv(
            session,
            csv_path,
            allow_missing=args.allow_missing,
        )

    await engine.dispose()
    logger.info("fundamentals.import.completed", path=str(csv_path), **result.__dict__)
    print(
        "Fundamentals import completed: "
        f"{result.rows_read} rows read, "
        f"{result.financials_created} financial rows created, "
        f"{result.financials_updated} financial rows updated, "
        f"{result.rows_skipped} rows skipped."
    )


if __name__ == "__main__":
    asyncio.run(main())
