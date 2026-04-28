"""B3 listed-company collection helpers."""

from __future__ import annotations

import base64
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from warren_ingestion.fetching import fetch_with_cache
from warren_ingestion.models import B3TickerRow, KnownCompany
from warren_ingestion.normalization import normalize_cnpj, normalize_ticker
from warren_ingestion.validation import is_valid_b3_ticker


B3_COMPANY_CALL_BASE_URL = (
    "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall"
)
B3_LISTED_COMPANIES_PAGE_URL = (
    "https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/"
    "renda-variavel/empresas-listadas.htm"
)
B3_OUTPUT_FIELDS = (
    "ticker",
    "name",
    "cnpj",
    "sector",
    "segment",
    "asset_type",
    "source_url",
    "source_updated_at",
)


@dataclass(frozen=True)
class B3CollectionResult:
    output_path: str
    initial_pages: int
    detail_requests: int
    ticker_rows: int


def collect_b3_tickers(
    output_path: Path,
    *,
    cache_dir: Path,
    known_companies: list[KnownCompany] | None = None,
    page_size: int = 120,
    delay_seconds: float = 1.0,
    max_age_hours: int = 24,
    limit_companies: int | None = None,
) -> B3CollectionResult:
    """Collect B3 ticker rows from cached official JSON endpoints."""
    max_age_seconds = max_age_hours * 60 * 60
    known_cnpjs = {company.cnpj for company in known_companies or []}

    first_page = _fetch_initial_page(
        page_number=1,
        page_size=page_size,
        cache_dir=cache_dir,
        max_age_seconds=max_age_seconds,
    )
    total_pages = _total_pages(first_page)
    initial_records = list(first_page.get("results", []))

    for page_number in range(2, total_pages + 1):
        _sleep_between_requests(delay_seconds)
        page = _fetch_initial_page(
            page_number=page_number,
            page_size=page_size,
            cache_dir=cache_dir,
            max_age_seconds=max_age_seconds,
        )
        initial_records.extend(page.get("results", []))

    candidates = _filter_detail_candidates(initial_records, known_cnpjs)
    if limit_companies is not None:
        candidates = candidates[:limit_companies]

    ticker_rows: list[B3TickerRow] = []
    detail_requests = 0
    for company in candidates:
        code_cvm = str(company.get("codeCVM", "")).strip()
        if not code_cvm:
            continue

        _sleep_between_requests(delay_seconds)
        detail = _fetch_company_detail(
            code_cvm=code_cvm,
            cache_dir=cache_dir,
            max_age_seconds=max_age_seconds,
        )
        detail_requests += 1
        ticker_rows.extend(_detail_to_ticker_rows(detail))

    _write_b3_rows(output_path, ticker_rows)
    return B3CollectionResult(
        output_path=str(output_path),
        initial_pages=total_pages,
        detail_requests=detail_requests,
        ticker_rows=len(ticker_rows),
    )


def _fetch_initial_page(
    *,
    page_number: int,
    page_size: int,
    cache_dir: Path,
    max_age_seconds: int,
) -> dict[str, object]:
    params = {
        "language": "pt-br",
        "pageNumber": page_number,
        "pageSize": page_size,
        "company": "",
    }
    path = cache_dir / "b3" / "initial" / f"page_size_{page_size}" / f"page_{page_number:04d}.json"
    result = fetch_with_cache(
        f"{B3_COMPANY_CALL_BASE_URL}/GetInitialCompanies/{_encode_b3_params(params)}",
        path,
        max_age_seconds=max_age_seconds,
    )
    return json.loads(Path(result.output_path).read_text(encoding="utf-8"))


def _fetch_company_detail(
    *,
    code_cvm: str,
    cache_dir: Path,
    max_age_seconds: int,
) -> dict[str, object]:
    params = {"codeCVM": code_cvm, "language": "pt-br"}
    path = cache_dir / "b3" / "detail" / f"{quote(code_cvm, safe='')}.json"
    result = fetch_with_cache(
        f"{B3_COMPANY_CALL_BASE_URL}/GetDetail/{_encode_b3_params(params)}",
        path,
        max_age_seconds=max_age_seconds,
    )
    return json.loads(Path(result.output_path).read_text(encoding="utf-8"))


def _encode_b3_params(params: dict[str, object]) -> str:
    # B3's public frontend encodes the Python-style dict representation.
    payload = str(params).encode("ascii")
    return base64.b64encode(payload).decode("ascii")


def _total_pages(page: dict[str, object]) -> int:
    total_pages = page.get("page", {}).get("totalPages")
    if not total_pages:
        return 1
    return int(total_pages)


def _filter_detail_candidates(
    records: list[object],
    known_cnpjs: set[str],
) -> list[dict[str, object]]:
    candidates = []
    seen_code_cvm: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        code_cvm = str(record.get("codeCVM", "")).strip()
        if not code_cvm or code_cvm in seen_code_cvm:
            continue
        cnpj = normalize_cnpj(str(record.get("cnpj", "")))
        if known_cnpjs and cnpj not in known_cnpjs:
            continue
        if str(record.get("status", "")).upper() != "A":
            continue
        if str(record.get("type", "")).strip() != "1":
            continue
        candidates.append(record)
        seen_code_cvm.add(code_cvm)
    return candidates


def _detail_to_ticker_rows(detail: dict[str, object]) -> list[B3TickerRow]:
    rows = []
    company_name = str(detail.get("companyName", "")).strip()
    cnpj = normalize_cnpj(str(detail.get("cnpj", "")))
    sector, segment = _split_industry_classification(
        str(detail.get("industryClassification", "")).strip()
    )
    source_updated_at = str(detail.get("lastDate", "")).strip() or None

    for ticker in _extract_tickers(detail):
        rows.append(
            B3TickerRow(
                ticker=ticker,
                name=company_name,
                cnpj=cnpj,
                sector=sector,
                segment=segment,
                asset_type="STOCK",
                source_url=B3_LISTED_COMPANIES_PAGE_URL,
                source_updated_at=source_updated_at,
            )
        )
    return rows


def _extract_tickers(detail: dict[str, object]) -> list[str]:
    tickers = []
    for value in (detail.get("code"),):
        ticker = normalize_ticker(str(value or ""))
        if is_valid_b3_ticker(ticker):
            tickers.append(ticker)

    other_codes = detail.get("otherCodes", [])
    if isinstance(other_codes, list):
        for item in other_codes:
            if not isinstance(item, dict):
                continue
            ticker = normalize_ticker(str(item.get("code", "")))
            if is_valid_b3_ticker(ticker):
                tickers.append(ticker)

    return sorted(set(tickers))


def _split_industry_classification(value: str) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    parts = [part.strip() for part in value.split("/") if part.strip()]
    if not parts:
        return None, None
    return parts[0], parts[-1] if len(parts) > 1 else None


def _write_b3_rows(path: Path, rows: list[B3TickerRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=B3_OUTPUT_FIELDS)
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item.ticker):
            writer.writerow(
                {
                    "ticker": row.ticker,
                    "name": row.name,
                    "cnpj": row.cnpj,
                    "sector": row.sector,
                    "segment": row.segment,
                    "asset_type": row.asset_type,
                    "source_url": row.source_url,
                    "source_updated_at": row.source_updated_at,
                }
            )


def _sleep_between_requests(delay_seconds: float) -> None:
    if delay_seconds > 0:
        time.sleep(delay_seconds)
