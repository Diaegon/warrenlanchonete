# Processed Fundamentals Data

Place the production fundamentals file here:

```text
fundamentals.csv
```

Expected header:

```csv
ticker,year,roe,lucro_liquido,margem_liquida,receita_liquida,divida_liquida,ebitda,divida_ebitda,market_cap,p_l,cagr_lucro
```

Rules:

- `ticker` must already exist in the backend `companies` table.
- `year` is required.
- Empty numeric cells are imported as `NULL`.
- Percent fields are stored as percentage values, not fractions. Use `28.5`
  for `28.5%`, not `0.285`.
- Monetary fields are BRL values with no thousands separators.

Example:

```csv
ticker,year,roe,lucro_liquido,margem_liquida,receita_liquida,divida_liquida,ebitda,divida_ebitda,market_cap,p_l,cagr_lucro
WEGE3,2024,28.5,5789000000,15.2,38090000000,1500000000,7600000000,0.4,158000000000,27.3,18.3
```

Manual import:

```bash
cd warren-backend
uv run python -m app.db.import_fundamentals --path ../warren-ingestion/data/processed/fundamentals.csv
```

## Current Gather Pipeline

Annual accounting fundamentals come from CVM DFP ZIP files:

```bash
cd warren-ingestion
uv run warren-ingestion fetch-cvm-dfp --years 2019 2020 2021 2022 2023 2024
uv run warren-ingestion build-fundamentals \
  --b3-file data/cache/b3/tickers.csv \
  --dfp-zips \
    data/cache/cvm/dfp/dfp_cia_aberta_2019.zip \
    data/cache/cvm/dfp/dfp_cia_aberta_2020.zip \
    data/cache/cvm/dfp/dfp_cia_aberta_2021.zip \
    data/cache/cvm/dfp/dfp_cia_aberta_2022.zip \
    data/cache/cvm/dfp/dfp_cia_aberta_2023.zip \
    data/cache/cvm/dfp/dfp_cia_aberta_2024.zip \
  --output data/processed/fundamentals.csv
```

The first gathered file contains:

```text
3047 annual rows
523 matched stock tickers
2019-2024 DFP years
```

Current CVM-derived fields:

```text
lucro_liquido
receita_liquida
roe
margem_liquida
divida_liquida
cagr_lucro
```

Current blank fields:

```text
ebitda
divida_ebitda
market_cap
p_l
```

Those need either a more specific EBITDA derivation/source or market data
inputs such as price and shares outstanding.
