"""Dry-run validation for B3 ticker rows against known companies."""

from __future__ import annotations

import re

from warren_ingestion.models import (
    B3TickerRow,
    BackendCompanyRow,
    CvmCompany,
    KnownCompany,
    ValidationReport,
)
from warren_ingestion.normalization import is_valid_cnpj, normalize_name


_B3_TICKER_RE = re.compile(r"^[A-Z]{4}[0-9]{1,2}[A-Z]?$")
_ACTIVE_CVM_WORDS = ("ATIVO", "REGISTRO ATIVO")


def validate_tickers(
    known_companies: list[KnownCompany],
    b3_rows: list[B3TickerRow],
    cvm_companies: list[CvmCompany] | None = None,
) -> ValidationReport:
    """Build a non-destructive validation report for B3 ticker enrichment."""
    known_by_cnpj = {company.cnpj: company for company in known_companies}
    known_by_name = {normalize_name(company.name): company for company in known_companies}
    cvm_by_cnpj = {company.cnpj: company for company in cvm_companies or []}
    matched_known_cnpjs: set[str] = set()
    seen_tickers: set[str] = set()

    report = ValidationReport(total_b3_rows=len(b3_rows))

    for row in b3_rows:
        row_dict = _b3_row_dict(row)
        if not is_valid_b3_ticker(row.ticker):
            report.invalid_tickers.append(row_dict)

        match = None
        if is_valid_cnpj(row.cnpj):
            match = known_by_cnpj.get(row.cnpj)
        else:
            report.missing_cnpj_rows.append(row_dict)

        if match:
            report.matched_by_cnpj += 1
            matched_known_cnpjs.add(match.cnpj)
        else:
            match = known_by_name.get(normalize_name(row.name))
            if match:
                report.matched_by_name += 1
                matched_known_cnpjs.add(match.cnpj)
            else:
                report.unmatched_b3_rows.append(row_dict)
                continue

        cvm_company = cvm_by_cnpj.get(match.cnpj)
        if cvm_company and not _looks_active(cvm_company.status):
            report.cvm_status_warnings.append(
                {
                    "ticker": row.ticker,
                    "cnpj": match.cnpj,
                    "name": row.name,
                    "cvm_status": cvm_company.status,
                }
            )

        if row.ticker not in seen_tickers:
            report.backend_rows.append(
                BackendCompanyRow(
                    ticker=row.ticker,
                    name=row.name,
                    sector=row.sector,
                    segment=row.segment,
                    asset_type=row.asset_type or "STOCK",
                )
            )
            seen_tickers.add(row.ticker)

    for company in known_companies:
        if company.cnpj not in matched_known_cnpjs:
            report.known_companies_without_ticker.append(
                {"cnpj": company.cnpj, "name": company.name}
            )

    report.backend_rows.sort(key=lambda item: item.ticker)
    return report


def _looks_active(status: str | None) -> bool:
    if not status:
        return True
    normalized = normalize_name(status)
    return any(word in normalized for word in _ACTIVE_CVM_WORDS)


def is_valid_b3_ticker(value: str) -> bool:
    """Return True for common B3 equity ticker symbols."""
    return bool(_B3_TICKER_RE.match(value))


def _b3_row_dict(row: B3TickerRow) -> dict[str, str | None]:
    return {
        "ticker": row.ticker,
        "name": row.name,
        "cnpj": row.cnpj,
        "source_url": row.source_url,
        "source_updated_at": row.source_updated_at,
    }
