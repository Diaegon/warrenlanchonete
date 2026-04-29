"""Command-line entry points for ingestion dry runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from warren_ingestion.b3 import collect_b3_tickers
from warren_ingestion.exporters import export_backend_rows_csv
from warren_ingestion.fetching import CVM_CIA_ABERTA_URL, fetch_with_cache
from warren_ingestion.fundamentals import build_fundamentals_csv, fetch_dfp_zips
from warren_ingestion.file_readers import (
    read_b3_tickers,
    read_cvm_companies,
    read_known_companies,
)
from warren_ingestion.validation import validate_tickers


def main() -> None:
    parser = argparse.ArgumentParser(prog="warren-ingestion")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-b3-tickers",
        help="Validate cached B3 ticker rows against known company CNPJs.",
    )
    validate_parser.add_argument("--known-companies", required=True, type=Path)
    validate_parser.add_argument("--b3-file", required=True, type=Path)
    validate_parser.add_argument("--cvm-file", type=Path)
    validate_parser.add_argument("--output", type=Path)
    validate_parser.set_defaults(handler=_validate_b3_tickers)

    fetch_cvm_parser = subparsers.add_parser(
        "fetch-cvm-cia-aberta",
        help="Download the official CVM public-company CSV with a local cache.",
    )
    fetch_cvm_parser.add_argument("--cache-dir", type=Path, default=Path("data/cache"))
    fetch_cvm_parser.add_argument("--max-age-hours", type=int, default=24)
    fetch_cvm_parser.set_defaults(handler=_fetch_cvm_cia_aberta)

    fetch_url_parser = subparsers.add_parser(
        "fetch-url",
        help="Fetch a reviewed structured source URL with the same polite cache policy.",
    )
    fetch_url_parser.add_argument("--url", required=True)
    fetch_url_parser.add_argument("--output", required=True, type=Path)
    fetch_url_parser.add_argument("--max-age-hours", type=int, default=24)
    fetch_url_parser.set_defaults(handler=_fetch_url)

    b3_parser = subparsers.add_parser(
        "collect-b3-tickers",
        help="Collect B3 ticker rows from official cached JSON endpoints.",
    )
    b3_parser.add_argument("--output", type=Path, default=Path("data/cache/b3/tickers.csv"))
    b3_parser.add_argument("--cache-dir", type=Path, default=Path("data/cache"))
    b3_parser.add_argument("--known-companies", type=Path)
    b3_parser.add_argument("--page-size", type=int, default=120)
    b3_parser.add_argument("--delay-seconds", type=float, default=1.0)
    b3_parser.add_argument("--max-age-hours", type=int, default=24)
    b3_parser.add_argument("--limit-companies", type=int)
    b3_parser.set_defaults(handler=_collect_b3_tickers)

    export_parser = subparsers.add_parser(
        "export-backend-companies",
        help="Export backend-compatible company rows from a dry-run JSON report.",
    )
    export_parser.add_argument("--report", required=True, type=Path)
    export_parser.add_argument("--output", required=True, type=Path)
    export_parser.set_defaults(handler=_export_backend_companies)

    fetch_dfp_parser = subparsers.add_parser(
        "fetch-cvm-dfp",
        help="Download official CVM DFP ZIPs for annual fundamentals.",
    )
    fetch_dfp_parser.add_argument("--years", nargs="+", required=True, type=int)
    fetch_dfp_parser.add_argument("--cache-dir", type=Path, default=Path("data/cache"))
    fetch_dfp_parser.add_argument("--max-age-hours", type=int, default=24 * 7)
    fetch_dfp_parser.set_defaults(handler=_fetch_cvm_dfp)

    fundamentals_parser = subparsers.add_parser(
        "build-fundamentals",
        help="Build backend fundamentals.csv from cached CVM DFP ZIPs.",
    )
    fundamentals_parser.add_argument(
        "--b3-file",
        type=Path,
        default=Path("data/cache/b3/tickers.csv"),
    )
    fundamentals_parser.add_argument("--dfp-zips", nargs="+", required=True, type=Path)
    fundamentals_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/fundamentals.csv"),
    )
    fundamentals_parser.set_defaults(handler=_build_fundamentals)

    args = parser.parse_args()
    args.handler(args)


def _validate_b3_tickers(args: argparse.Namespace) -> None:
    known_companies = read_known_companies(args.known_companies)
    b3_rows = read_b3_tickers(args.b3_file)
    cvm_companies = read_cvm_companies(args.cvm_file) if args.cvm_file else None

    report = validate_tickers(
        known_companies=known_companies,
        b3_rows=b3_rows,
        cvm_companies=cvm_companies,
    )
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


def _fetch_cvm_cia_aberta(args: argparse.Namespace) -> None:
    result = fetch_with_cache(
        CVM_CIA_ABERTA_URL,
        args.cache_dir / "cvm" / "cad_cia_aberta.csv",
        max_age_seconds=args.max_age_hours * 60 * 60,
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


def _fetch_url(args: argparse.Namespace) -> None:
    result = fetch_with_cache(
        args.url,
        args.output,
        max_age_seconds=args.max_age_hours * 60 * 60,
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


def _collect_b3_tickers(args: argparse.Namespace) -> None:
    known_companies = (
        read_known_companies(args.known_companies) if args.known_companies else None
    )
    result = collect_b3_tickers(
        output_path=args.output,
        cache_dir=args.cache_dir,
        known_companies=known_companies,
        page_size=args.page_size,
        delay_seconds=args.delay_seconds,
        max_age_hours=args.max_age_hours,
        limit_companies=args.limit_companies,
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


def _export_backend_companies(args: argparse.Namespace) -> None:
    rows_written = export_backend_rows_csv(args.report, args.output)
    print(
        json.dumps(
            {"output_path": str(args.output), "rows_written": rows_written},
            ensure_ascii=False,
            indent=2,
        )
    )


def _fetch_cvm_dfp(args: argparse.Namespace) -> None:
    paths = fetch_dfp_zips(
        args.years,
        cache_dir=args.cache_dir,
        max_age_hours=args.max_age_hours,
    )
    print(
        json.dumps(
            {"years": args.years, "paths": [str(path) for path in paths]},
            ensure_ascii=False,
            indent=2,
        )
    )


def _build_fundamentals(args: argparse.Namespace) -> None:
    result = build_fundamentals_csv(
        b3_tickers_path=args.b3_file,
        dfp_zip_paths=args.dfp_zips,
        output_path=args.output,
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
