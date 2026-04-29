"""Build backend fundamentals from official CVM DFP statement ZIPs."""

from __future__ import annotations

import csv
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from warren_ingestion.fetching import fetch_with_cache
from warren_ingestion.file_readers import read_b3_tickers
from warren_ingestion.normalization import normalize_cnpj


CVM_DFP_BASE_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS"
FUNDAMENTALS_FIELDS = (
    "ticker",
    "year",
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


@dataclass
class StatementValues:
    """Raw accounting values extracted from CVM statements for one company/year."""

    ticker: str
    year: int
    receita_liquida: Decimal | None = None
    lucro_liquido: Decimal | None = None
    patrimonio_liquido: Decimal | None = None
    caixa: Decimal | None = None
    divida_bruta: Decimal | None = None


@dataclass(frozen=True)
class FundamentalsBuildResult:
    """Output counts from building fundamentals.csv."""

    years_processed: int
    rows_written: int
    companies_matched: int
    output_path: str


def dfp_zip_url(year: int) -> str:
    """Return the official CVM DFP ZIP URL for a year."""
    return f"{CVM_DFP_BASE_URL}/dfp_cia_aberta_{year}.zip"


def fetch_dfp_zips(
    years: Iterable[int],
    *,
    cache_dir: Path,
    max_age_hours: int,
) -> list[Path]:
    """Download official CVM DFP ZIPs into the local cache."""
    paths: list[Path] = []
    for year in years:
        output_path = cache_dir / "cvm" / "dfp" / f"dfp_cia_aberta_{year}.zip"
        fetch_with_cache(
            dfp_zip_url(year),
            output_path,
            max_age_seconds=max_age_hours * 60 * 60,
        )
        paths.append(output_path)
    return paths


def build_fundamentals_csv(
    *,
    b3_tickers_path: Path,
    dfp_zip_paths: Iterable[Path],
    output_path: Path,
) -> FundamentalsBuildResult:
    """Build backend-compatible fundamentals.csv from CVM DFP ZIPs."""
    cnpj_to_tickers = _load_cnpj_to_tickers(b3_tickers_path)
    values_by_key: dict[tuple[str, int], StatementValues] = {}
    years_processed: set[int] = set()

    for zip_path in dfp_zip_paths:
        year = _year_from_zip_name(zip_path)
        years_processed.add(year)
        _read_dfp_zip(zip_path, year, cnpj_to_tickers, values_by_key)

    rows = [_fundamentals_row(values_by_key[key], values_by_key) for key in sorted(values_by_key)]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FUNDAMENTALS_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return FundamentalsBuildResult(
        years_processed=len(years_processed),
        rows_written=len(rows),
        companies_matched=len({row["ticker"] for row in rows}),
        output_path=str(output_path),
    )


def _load_cnpj_to_tickers(path: Path) -> dict[str, list[str]]:
    cnpj_to_tickers: dict[str, list[str]] = {}
    for row in read_b3_tickers(path):
        cnpj = normalize_cnpj(row.cnpj)
        if not cnpj or row.asset_type != "STOCK":
            continue
        cnpj_to_tickers.setdefault(cnpj, [])
        if row.ticker not in cnpj_to_tickers[cnpj]:
            cnpj_to_tickers[cnpj].append(row.ticker)
    return cnpj_to_tickers


def _year_from_zip_name(path: Path) -> int:
    for part in path.stem.split("_"):
        if part.isdigit() and len(part) == 4:
            return int(part)
    raise ValueError(f"could not infer year from {path}")


def _read_dfp_zip(
    zip_path: Path,
    year: int,
    cnpj_to_tickers: dict[str, list[str]],
    values_by_key: dict[tuple[str, int], StatementValues],
) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in sorted(archive.namelist(), key=_statement_priority):
            member_lower = member.lower()
            if "_dre_" in member_lower and member_lower.endswith(".csv"):
                _read_statement_file(
                    archive,
                    member,
                    year,
                    cnpj_to_tickers,
                    values_by_key,
                    statement_type="DRE",
                )
            elif "_bpa_" in member_lower and member_lower.endswith(".csv"):
                _read_statement_file(
                    archive,
                    member,
                    year,
                    cnpj_to_tickers,
                    values_by_key,
                    statement_type="BPA",
                )
            elif "_bpp_" in member_lower and member_lower.endswith(".csv"):
                _read_statement_file(
                    archive,
                    member,
                    year,
                    cnpj_to_tickers,
                    values_by_key,
                    statement_type="BPP",
                )


def _statement_priority(member: str) -> tuple[int, str]:
    """Read individual statements before consolidated ones so CON wins."""
    member_lower = member.lower()
    rank = 1 if "_con_" in member_lower else 0
    return rank, member_lower


def _read_statement_file(
    archive: zipfile.ZipFile,
    member: str,
    year: int,
    cnpj_to_tickers: dict[str, list[str]],
    values_by_key: dict[tuple[str, int], StatementValues],
    *,
    statement_type: str,
) -> None:
    with archive.open(member) as raw_file:
        text = raw_file.read().decode("latin-1")
    reader = csv.DictReader(text.splitlines(), delimiter=";")
    for row in reader:
        if not _is_latest_period(row):
            continue
        cnpj = normalize_cnpj(row.get("CNPJ_CIA") or "")
        tickers = cnpj_to_tickers.get(cnpj)
        if not tickers:
            continue
        account_code = (row.get("CD_CONTA") or "").strip()
        account_name = (row.get("DS_CONTA") or "").strip()
        value = _parse_cvm_decimal(row.get("VL_CONTA"), row.get("ESCALA_MOEDA"))
        if value is None:
            continue

        for ticker in tickers:
            key = (ticker, year)
            values = values_by_key.setdefault(key, StatementValues(ticker=ticker, year=year))
            _apply_account_value(values, statement_type, account_code, account_name, value)


def _is_latest_period(row: dict[str, str]) -> bool:
    order = _normalize_text(row.get("ORDEM_EXERC") or "")
    return not order or order == "ultimo"


def _parse_cvm_decimal(value: str | None, scale: str | None) -> Decimal | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = Decimal(value.strip().replace(",", "."))
    except InvalidOperation:
        return None
    scale_text = _normalize_text(scale or "")
    if "mil" in scale_text:
        return parsed * Decimal("1000")
    return parsed


def _apply_account_value(
    values: StatementValues,
    statement_type: str,
    account_code: str,
    account_name: str,
    value: Decimal,
) -> None:
    normalized_name = _normalize_text(account_name)
    if statement_type == "DRE":
        if account_code == "3.01" or normalized_name.startswith("receita de venda"):
            values.receita_liquida = value
        elif (
            account_code in {"3.11", "3.09"}
            or "lucro/prejuizo consolidado" in normalized_name
        ):
            values.lucro_liquido = value
    elif statement_type == "BPA":
        if account_code == "1.01.01" or "caixa e equivalentes" in normalized_name:
            values.caixa = value
    elif statement_type == "BPP":
        if account_code in {"2.03", "2.07"}:
            values.patrimonio_liquido = value
        elif _is_debt_account(account_code, normalized_name):
            values.divida_bruta = (values.divida_bruta or Decimal("0")) + value


def _is_debt_account(account_code: str, normalized_name: str) -> bool:
    if account_code in {"2.01.04", "2.02.01"}:
        return True
    debt_terms = ("emprestimos", "financiamentos", "debentures", "arrendamento")
    return any(term in normalized_name for term in debt_terms)


def _fundamentals_row(
    values: StatementValues,
    values_by_key: dict[tuple[str, int], StatementValues],
) -> dict[str, str]:
    divida_liquida = None
    if values.divida_bruta is not None and values.caixa is not None:
        divida_liquida = values.divida_bruta - values.caixa

    roe = _percentage(values.lucro_liquido, values.patrimonio_liquido)
    margem_liquida = _percentage(values.lucro_liquido, values.receita_liquida)
    cagr_lucro = _profit_cagr(values, values_by_key)

    return {
        "ticker": values.ticker,
        "year": str(values.year),
        "roe": _format_decimal(roe),
        "lucro_liquido": _format_decimal(values.lucro_liquido),
        "margem_liquida": _format_decimal(margem_liquida),
        "receita_liquida": _format_decimal(values.receita_liquida),
        "divida_liquida": _format_decimal(divida_liquida),
        "ebitda": "",
        "divida_ebitda": "",
        "market_cap": "",
        "p_l": "",
        "cagr_lucro": _format_decimal(cagr_lucro),
    }


def _percentage(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator in (None, Decimal("0")):
        return None
    return (numerator / denominator) * Decimal("100")


def _profit_cagr(
    values: StatementValues,
    values_by_key: dict[tuple[str, int], StatementValues],
) -> Decimal | None:
    current_profit = values.lucro_liquido
    prior = values_by_key.get((values.ticker, values.year - 5))
    prior_profit = prior.lucro_liquido if prior else None
    if current_profit is None or prior_profit is None or current_profit <= 0 or prior_profit <= 0:
        return None
    ratio = float(current_profit / prior_profit)
    return Decimal(str(((ratio ** (1 / 5)) - 1) * 100))


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return str(value.quantize(Decimal("0.0001")).normalize())


def _normalize_text(value: str) -> str:
    normalized = value.strip().lower()
    replacements = {
        "á": "a",
        "à": "a",
        "â": "a",
        "ã": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
        "�": "",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized
