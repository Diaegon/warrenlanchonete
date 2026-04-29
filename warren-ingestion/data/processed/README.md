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
