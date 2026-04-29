"""Starter database seed data for local development and smoke tests.

Run after Alembic migrations:
    uv run python -m app.db.seed
"""
from __future__ import annotations

import asyncio
import csv
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.company import Company
from app.models.financial import Financial

logger = structlog.get_logger(__name__)

DEV_DATABASE_URL = "postgresql://warren:password@localhost:5432/warren"
B3_TICKERS_CSV = Path("../warren-ingestion/data/cache/b3/tickers.csv")


def _load_b3_company_rows(path: Path | None = None) -> tuple[dict[str, Any], ...]:
    """Load backend company rows from the B3 ingestion cache if available."""
    csv_path = path or Path(os.environ.get("B3_TICKERS_CSV", B3_TICKERS_CSV))
    if not csv_path.exists():
        logger.warning("database.seed.b3_cache_missing", path=str(csv_path))
        return ()

    rows: list[dict[str, Any]] = []
    seen_tickers: set[str] = set()
    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            ticker = (row.get("ticker") or "").strip().upper()
            name = (row.get("name") or "").strip()
            if not ticker or not name or ticker in seen_tickers:
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "sector": (row.get("sector") or "").strip() or None,
                    "segment": (row.get("segment") or "").strip() or None,
                    "asset_type": (row.get("asset_type") or "STOCK").strip().upper(),
                }
            )
            seen_tickers.add(ticker)

    return tuple(sorted(rows, key=lambda item: item["ticker"]))


FALLBACK_COMPANIES: tuple[dict[str, Any], ...] = (
    {
        "ticker": "WEGE3",
        "name": "WEG S.A.",
        "sector": "Industrial",
        "segment": "Máquinas e Equipamentos",
        "asset_type": "STOCK",
    },
    {
        "ticker": "PETR4",
        "name": "Petróleo Brasileiro S.A.",
        "sector": "Energia",
        "segment": "Petróleo, Gás e Biocombustíveis",
        "asset_type": "STOCK",
    },
    {
        "ticker": "MXRF11",
        "name": "Maxi Renda Fundo de Investimento Imobiliário",
        "sector": "FII",
        "segment": "Recebíveis Imobiliários",
        "asset_type": "FII",
    },
    {
        "ticker": "TESOURO",
        "name": "Tesouro Direto",
        "sector": "Renda Fixa",
        "segment": "Títulos Públicos",
        "asset_type": "TESOURO",
    },
)


def _starter_companies() -> tuple[dict[str, Any], ...]:
    """Return B3 cache rows plus non-B3 starter assets."""
    b3_rows = _load_b3_company_rows()
    rows_by_ticker = {row["ticker"]: row for row in FALLBACK_COMPANIES}
    for row in b3_rows:
        rows_by_ticker[row["ticker"]] = row
    rows_by_ticker["TESOURO"] = {
        "ticker": "TESOURO",
        "name": "Tesouro Direto",
        "sector": "Renda Fixa",
        "segment": "Títulos Públicos",
        "asset_type": "TESOURO",
    }
    return tuple(rows_by_ticker[ticker] for ticker in sorted(rows_by_ticker))


STARTER_FINANCIALS: tuple[dict[str, Any], ...] = (
    {
        "ticker": "WEGE3",
        "year": 2024,
        "roe": Decimal("28.5000"),
        "lucro_liquido": Decimal("5789000000.00"),
        "margem_liquida": Decimal("15.2000"),
        "receita_liquida": Decimal("38090000000.00"),
        "divida_liquida": Decimal("1500000000.00"),
        "ebitda": Decimal("7600000000.00"),
        "divida_ebitda": Decimal("0.4000"),
        "market_cap": Decimal("158000000000.00"),
        "p_l": Decimal("27.3000"),
        "cagr_lucro": Decimal("18.3000"),
    },
    {
        "ticker": "PETR4",
        "year": 2024,
        "roe": Decimal("22.1000"),
        "lucro_liquido": Decimal("36700000000.00"),
        "margem_liquida": Decimal("12.5000"),
        "receita_liquida": Decimal("490000000000.00"),
        "divida_liquida": Decimal("247000000000.00"),
        "ebitda": Decimal("274000000000.00"),
        "divida_ebitda": Decimal("1.8000"),
        "market_cap": Decimal("498000000000.00"),
        "p_l": Decimal("7.2000"),
        "cagr_lucro": None,
    },
    {
        "ticker": "MXRF11",
        "year": 2024,
        "roe": Decimal("9.0000"),
        "lucro_liquido": None,
        "margem_liquida": None,
        "receita_liquida": None,
        "divida_liquida": None,
        "ebitda": None,
        "divida_ebitda": None,
        "market_cap": Decimal("3200000000.00"),
        "p_l": None,
        "cagr_lucro": None,
    },
)


@dataclass(frozen=True)
class SeedResult:
    """Counts of rows created or updated by a seed run."""

    companies_created: int = 0
    companies_updated: int = 0
    financials_created: int = 0
    financials_updated: int = 0


def _make_async_url(url: str) -> str:
    """Convert common sync database URLs to async SQLAlchemy URLs."""
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
            "postgres://", "postgresql+asyncpg://", 1
        )
    if url.startswith("sqlite://") and "aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


async def seed_database(session: AsyncSession) -> SeedResult:
    """Upsert starter companies and financial rows.

    Args:
        session: Open SQLAlchemy async session.

    Returns:
        Counts for created and updated rows.
    """
    companies_created = 0
    companies_updated = 0
    financials_created = 0
    financials_updated = 0
    companies_by_ticker: dict[str, Company] = {}

    for row in _starter_companies():
        ticker = row["ticker"]
        company = await session.scalar(select(Company).where(Company.ticker == ticker))
        if company is None:
            company = Company(**row)
            session.add(company)
            companies_created += 1
        else:
            for field, value in row.items():
                setattr(company, field, value)
            companies_updated += 1
        companies_by_ticker[ticker] = company

    await session.flush()

    for row in STARTER_FINANCIALS:
        ticker = row["ticker"]
        company = companies_by_ticker.get(ticker)
        if company is None:
            logger.warning("database.seed.financial_skipped", ticker=ticker, reason="company_missing")
            continue
        year = row["year"]
        values = {key: value for key, value in row.items() if key != "ticker"}
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

    return SeedResult(
        companies_created=companies_created,
        companies_updated=companies_updated,
        financials_created=financials_created,
        financials_updated=financials_updated,
    )


async def main() -> None:
    """Seed the configured database."""
    load_dotenv()
    database_url = os.environ.get("DATABASE_URL", DEV_DATABASE_URL)
    engine = create_async_engine(_make_async_url(database_url), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        result = await seed_database(session)

    await engine.dispose()
    logger.info("database.seed.completed", **result.__dict__)
    print(
        "Seed completed: "
        f"{result.companies_created} companies created, "
        f"{result.companies_updated} companies updated, "
        f"{result.financials_created} financial rows created, "
        f"{result.financials_updated} financial rows updated."
    )


if __name__ == "__main__":
    asyncio.run(main())
