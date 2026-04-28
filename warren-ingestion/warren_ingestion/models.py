"""Data objects used by the ticker ingestion dry run."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class KnownCompany:
    name: str
    cnpj: str


@dataclass(frozen=True)
class B3TickerRow:
    ticker: str
    name: str
    cnpj: str
    sector: str | None = None
    segment: str | None = None
    asset_type: str = "STOCK"
    source_url: str | None = None
    source_updated_at: str | None = None


@dataclass(frozen=True)
class CvmCompany:
    name: str
    cnpj: str
    status: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class BackendCompanyRow:
    ticker: str
    name: str
    sector: str | None
    segment: str | None
    asset_type: str


@dataclass
class ValidationReport:
    total_b3_rows: int = 0
    matched_by_cnpj: int = 0
    matched_by_name: int = 0
    unmatched_b3_rows: list[dict[str, str | None]] = field(default_factory=list)
    known_companies_without_ticker: list[dict[str, str]] = field(default_factory=list)
    invalid_tickers: list[dict[str, str | None]] = field(default_factory=list)
    missing_cnpj_rows: list[dict[str, str | None]] = field(default_factory=list)
    cvm_status_warnings: list[dict[str, str | None]] = field(default_factory=list)
    backend_rows: list[BackendCompanyRow] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Serialize report to plain JSON-compatible objects."""
        data = asdict(self)
        data["backend_rows"] = [asdict(row) for row in self.backend_rows]
        return data
