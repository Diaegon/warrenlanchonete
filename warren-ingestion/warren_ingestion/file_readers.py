"""Flexible readers for cached CSV files used by the dry-run validator."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from warren_ingestion.models import B3TickerRow, CvmCompany, KnownCompany
from warren_ingestion.normalization import normalize_cnpj, normalize_ticker


KNOWN_COMPANY_NAME_FIELDS = ("name", "company_name", "nome", "razao_social", "denom_social")
KNOWN_COMPANY_CNPJ_FIELDS = ("cnpj", "cnpj_cia", "cnpj_companhia")

B3_TICKER_FIELDS = (
    "ticker",
    "symbol",
    "codneg",
    "codigo_negociacao",
    "cod_negociacao",
    "codigo",
    "code",
    "trading_code",
    "securityCode",
    "security_code",
)
B3_NAME_FIELDS = (
    "name",
    "nome",
    "company_name",
    "companyName",
    "empresa",
    "trading_name",
    "tradingName",
    "nome_pregao",
)
B3_CNPJ_FIELDS = ("cnpj", "cnpj_cia", "cnpj_companhia")
B3_SECTOR_FIELDS = ("sector", "setor", "setor_atividade", "economic_sector")
B3_SEGMENT_FIELDS = ("segment", "segmento", "subsetor", "subsector")
B3_ASSET_TYPE_FIELDS = ("asset_type", "tipo_ativo", "type")
B3_SOURCE_URL_FIELDS = ("source_url", "sourceUrl", "url", "link")
B3_UPDATED_FIELDS = (
    "source_updated_at",
    "sourceUpdatedAt",
    "updated_at",
    "updatedAt",
    "data_atualizacao",
    "dt_atualizacao",
)

CVM_NAME_FIELDS = ("denom_social", "denom_comerc", "name", "nome", "company_name")
CVM_CNPJ_FIELDS = ("cnpj_cia", "cnpj", "cnpj_companhia")
CVM_STATUS_FIELDS = ("sit", "situacao", "status")
CVM_UPDATED_FIELDS = ("dt_reg", "dt_ini_sit", "updated_at", "data_atualizacao")


def read_known_companies(path: Path) -> list[KnownCompany]:
    rows = _read_csv_dicts(path)
    companies = []
    for row in rows:
        name = _pick(row, KNOWN_COMPANY_NAME_FIELDS)
        cnpj = normalize_cnpj(_pick(row, KNOWN_COMPANY_CNPJ_FIELDS))
        if name and cnpj:
            companies.append(KnownCompany(name=name, cnpj=cnpj))
    return companies


def read_b3_tickers(path: Path) -> list[B3TickerRow]:
    rows = _read_structured_dicts(path)
    tickers = []
    for row in rows:
        ticker = normalize_ticker(_pick(row, B3_TICKER_FIELDS))
        name = _pick(row, B3_NAME_FIELDS)
        if not ticker or not name:
            continue
        tickers.append(
            B3TickerRow(
                ticker=ticker,
                name=name,
                cnpj=normalize_cnpj(_pick(row, B3_CNPJ_FIELDS)),
                sector=_pick(row, B3_SECTOR_FIELDS) or None,
                segment=_pick(row, B3_SEGMENT_FIELDS) or None,
                asset_type=(_pick(row, B3_ASSET_TYPE_FIELDS) or "STOCK").upper(),
                source_url=_pick(row, B3_SOURCE_URL_FIELDS) or None,
                source_updated_at=_pick(row, B3_UPDATED_FIELDS) or None,
            )
        )
    return tickers


def read_cvm_companies(path: Path) -> list[CvmCompany]:
    rows = _read_csv_dicts(path)
    companies = []
    for row in rows:
        name = _pick(row, CVM_NAME_FIELDS)
        cnpj = normalize_cnpj(_pick(row, CVM_CNPJ_FIELDS))
        if name and cnpj:
            companies.append(
                CvmCompany(
                    name=name,
                    cnpj=cnpj,
                    status=_pick(row, CVM_STATUS_FIELDS) or None,
                    updated_at=_pick(row, CVM_UPDATED_FIELDS) or None,
                )
            )
    return companies


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                sample = file.read(4096)
                file.seek(0)
                dialect = _detect_csv_dialect(sample)
                reader = csv.DictReader(file, dialect=dialect)
                return [
                    {
                        _normalize_key(key): value.strip()
                        for key, value in row.items()
                    }
                    for row in reader
                ]
        except UnicodeDecodeError as exc:
            last_error = exc
    raise UnicodeDecodeError(
        last_error.encoding,
        last_error.object,
        last_error.start,
        last_error.end,
        last_error.reason,
    )


def _detect_csv_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;|\t")
    except csv.Error:
        delimiter = max((",", ";", "|", "\t"), key=sample.count)

        class FallbackDialect(csv.excel):
            pass

        FallbackDialect.delimiter = delimiter
        return FallbackDialect


def _read_structured_dicts(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".json":
        return _read_json_dicts(path)
    return _read_csv_dicts(path)


def _read_json_dicts(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = _extract_record_list(payload)
    return [_stringify_record(record) for record in records]


def _extract_record_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("results", "data", "items", "companies"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    assets = payload.get("assets")
    if isinstance(assets, dict):
        value = assets.get("stocks")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    return []


def _stringify_record(record: dict[str, Any]) -> dict[str, str]:
    return {
        _normalize_key(key): "" if value is None else str(value).strip()
        for key, value in record.items()
    }


def _pick(row: dict[str, str], names: Iterable[str]) -> str:
    for name in names:
        value = row.get(_normalize_key(name), "")
        if value:
            return value
    return ""


def _normalize_key(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower()
