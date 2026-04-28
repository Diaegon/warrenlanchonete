# B3 Tickers Ingestion Plan

## Scope

Collect tradable B3 ticker rows for companies already known by the project. The
first project dataset already contains company names and CNPJ values, so this
pipeline must enrich those companies with B3 ticker symbols and display names.

The backend currently stores one row per ticker in `companies`, with:

- `ticker`
- `name`
- `sector`
- `segment`
- `asset_type`

The ingestion step should keep CNPJ and source metadata during validation, but
the first backend load should still produce rows compatible with that table.

## Sources

### Primary: B3 Listed Companies

Use B3's official listed-companies source for tradable tickers. Prefer a
structured JSON/CSV endpoint used by B3 pages before scraping HTML.

Fields needed:

- ticker / trading code
- company name / trading name
- CNPJ, when available
- sector
- segment
- source URL
- source update date, when available

Before enabling live collection, check the relevant B3 `robots.txt`, page terms,
and endpoint behavior.

### Validation: CVM Open Data

Use CVM's structured open-data CSV for public-company registration validation.
This source is useful for CNPJ, legal company name, registration status, and
freshness. Use it to verify that B3 rows match the known company list.

Current CVM CSV:

```text
https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv
```

## Rate Limits And Cache

- Fetch B3 at most once per daily run.
- Keep a local cache of raw B3 and CVM files.
- Use a polite delay of at least 1 second between live HTTP requests.
- Retry transient failures at most 3 times with exponential backoff.
- Never use concurrent requests for this source in v1.

## ETL Steps

1. Extract cached B3 and CVM files.
2. Normalize CNPJ to 14 digits.
3. Normalize tickers to uppercase.
4. Normalize names only for matching; preserve source display names for output.
5. Match B3 rows to the existing company list by CNPJ first.
6. If CNPJ is missing, use normalized name matching as a fallback and flag it.
7. Produce a dry-run validation report.
8. Only after review, add a database loader that upserts backend-compatible rows.

## Validation Report

The dry-run report should show:

- total B3 ticker rows
- matched rows by CNPJ
- matched rows by name fallback
- unmatched B3 rows
- known companies without B3 ticker
- invalid ticker formats
- rows missing CNPJ
- backend-compatible company rows that would be loaded

## Storage Strategy

For v1, do not write directly to PostgreSQL. Generate a dry-run JSON report and
review the match quality first.

For the later load step, write one row per ticker:

```text
PETR3 | Petrobras | STOCK
PETR4 | Petrobras | STOCK
```

Keep source metadata in ingestion output or a separate staging table before
adding it to backend migrations.

## Current Commands

Fetch the CVM official CSV into the local cache:

```bash
warren-ingestion fetch-cvm-cia-aberta --cache-dir data/cache
```

Fetch a reviewed B3 structured endpoint after checking robots and terms:

```bash
warren-ingestion fetch-url \
  --url "https://reviewed-b3-endpoint.example/path" \
  --output data/cache/b3/listed_companies.json
```

Collect B3 ticker rows from B3's public listed-companies JSON endpoints. Use
`--known-companies` when the current CNPJ/name file is available so the detail
requests are limited to companies the project already tracks.

```bash
warren-ingestion collect-b3-tickers \
  --known-companies data/known_companies.csv \
  --output data/cache/b3/tickers.csv
```

For a smoke test, limit detail requests:

```bash
warren-ingestion collect-b3-tickers \
  --limit-companies 5 \
  --delay-seconds 1 \
  --output reports/b3_tickers_smoke.csv
```

Run the dry-run validation:

```bash
warren-ingestion validate-b3-tickers \
  --known-companies data/known_companies.csv \
  --b3-file data/cache/b3/listed_companies.csv \
  --cvm-file data/cache/cvm/cad_cia_aberta.csv \
  --output reports/b3_tickers_dry_run.json
```

Export only the backend-compatible `companies` rows from the reviewed report:

```bash
warren-ingestion export-backend-companies \
  --report reports/b3_tickers_dry_run.json \
  --output reports/backend_companies.csv
```
