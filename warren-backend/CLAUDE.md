# Warren Backend — Agent Guide

## RULE #1: TEST-DRIVEN DEVELOPMENT IS MANDATORY

**Every feature starts with a failing test. No exceptions.**

The workflow is always:
1. Write the test (it must fail — `pytest` confirms RED)
2. Write the minimum implementation to make it pass (GREEN)
3. Refactor (REFACTOR)

No implementation file is created without a corresponding test file already existing. Pull requests that add implementation code without tests will not be accepted. This applies to services, routers, RAG logic, prompt construction, and schema validation equally.

---

## Project Overview

FastAPI backend for Warren Lanchonete — a Brazilian retail portfolio analyzer powered by Buffett's shareholder letters (RAG) and GPT-4o. No external financial data calls at runtime; all fundamentals come from own PostgreSQL.

---

## How to Run

### Prerequisites

- Python 3.12+
- `uv` package manager (`pip install uv` or `curl -Lsf https://astral.sh/uv/install.sh | sh`)
- PostgreSQL running locally (or via Docker)
- ChromaDB persisted directory at `./rag_data/` (auto-created on first run)

### Install dependencies

```bash
uv sync
```

### Environment setup

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

Required variables:

```
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://user:password@localhost:5432/warren
CHROMA_PERSIST_DIR=./rag_data
```

### Run database migrations

```bash
uv run alembic upgrade head
```

### Seed starter database

Use this after migrations to create the first local dataset needed for smoke tests
and manual API testing. The seed is idempotent, so it is safe to rerun.

```bash
uv run python -m app.db.seed
```

Starter rows:
- `WEGE3` with 2024 financials
- `PETR4` with 2024 financials
- `MXRF11` with 2024 placeholder financials
- `TESOURO`

### Run ingestion (one-time + quarterly)

```bash
# Ingest Buffett PDFs into ChromaDB (run once after adding PDFs to rag_data/pdfs/)
uv run python -m app.rag.ingest

# Financial data is populated by the warren-ingestion repo (Scrapy spiders)
# This backend only ships a tiny starter seed for local smoke tests
```

### Start development server

```bash
uv run uvicorn app.main:app --reload --port 8000
```

API available at: `http://localhost:8000`
OpenAPI docs: `http://localhost:8000/docs`
Health check: `http://localhost:8000/health`

### Start production server (Hostinger VPS)

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## How to Test

### Run all tests

```bash
uv run pytest
```

### Run with coverage

```bash
uv run pytest --cov=app --cov-report=term-missing
```

### Run a specific module

```bash
uv run pytest tests/services/test_portfolio_service.py -v
```

### Run only fast tests (no I/O)

```bash
uv run pytest -m "not integration" -v
```

### Test configuration

Tests live in `tests/`. The `conftest.py` at the root of `tests/` provides shared fixtures.

**Mandatory fixtures (defined in `tests/conftest.py`):**

```python
# DB fixture — in-memory SQLite for unit tests, real PG for integration tests
@pytest.fixture
def db_session():
    ...

# ChromaDB fixture — ephemeral in-memory collection, not disk
@pytest.fixture
def chroma_client():
    ...

# Seeded ChromaDB with 3 fake Buffett passages
@pytest.fixture
def chroma_with_data(chroma_client):
    ...

# Async test client for FastAPI routes
@pytest.fixture
async def async_client(db_session, chroma_with_data):
    ...
```

**Test markers (defined in `pyproject.toml`):**

- `@pytest.mark.unit` — pure logic, no I/O, mocked dependencies
- `@pytest.mark.integration` — hits real DB or real ChromaDB (requires `.env`)
- `@pytest.mark.slow` — calls OpenAI (only run explicitly, always mocked in CI)

**OpenAI calls are always mocked in tests** using `unittest.mock.patch` or `pytest-mock`. Never make real API calls in the test suite.

---

## Module Structure

```
warren-backend/
├── app/
│   ├── main.py                  # FastAPI app factory, middleware, lifespan
│   ├── config.py                # pydantic-settings Settings class
│   ├── dependencies.py          # FastAPI dependency injection (get_db, get_rag)
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── portfolio.py         # POST /api/portfolio/analyze
│   │   └── companies.py         # GET /api/companies, GET /api/companies/{ticker}
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── portfolio_service.py # Orchestrates full analysis pipeline
│   │   ├── rag_service.py       # ChromaDB retrieval + query construction
│   │   ├── analysis_service.py  # GPT-4o prompts, per-asset + summary
│   │   └── pdf_service.py       # WeasyPrint + Jinja2 PDF generation
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── company.py           # SQLAlchemy Company ORM model
│   │   └── financial.py         # SQLAlchemy Financial ORM model
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── portfolio.py         # Request/response Pydantic schemas
│   │   └── company.py           # Company + Financial Pydantic schemas
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── client.py            # ChromaDB client singleton + collection accessor
│   │   └── ingest.py            # CLI: PDF → chunk → embed → ChromaDB
│   │
│   └── db/
│       ├── __init__.py
│       └── session.py           # SQLAlchemy async engine + session factory
│
├── migrations/                  # Alembic migration files
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── tests/
│   ├── conftest.py              # Shared fixtures (db_session, chroma_client, async_client)
│   ├── routers/
│   │   ├── test_portfolio.py
│   │   └── test_companies.py
│   ├── services/
│   │   ├── test_portfolio_service.py
│   │   ├── test_rag_service.py
│   │   ├── test_analysis_service.py
│   │   └── test_pdf_service.py
│   ├── schemas/
│   │   └── test_portfolio_schemas.py
│   └── rag/
│       └── test_ingest.py
│
├── templates/
│   └── report.html              # Jinja2 template for PDF export
│
├── rag_data/
│   ├── pdfs/                    # Raw Buffett shareholder letter PDFs (not git-tracked)
│   └── chroma/                  # ChromaDB persisted files (not git-tracked)
│
├── docs/
│   └── ARCHITECTURE.md          # Detailed design decisions (read this)
│
├── alembic.ini
├── pyproject.toml
├── .env.example
└── CLAUDE.md                    # This file
```

---

## Module Responsibilities

### `app/main.py`
FastAPI application factory. Registers all routers under the `/api` prefix. Configures CORS (frontend origin only). Sets up `lifespan` context manager that initializes the ChromaDB client on startup and disposes DB engine on shutdown. Adds request ID middleware for log correlation.

### `app/config.py`
Single `Settings` class using `pydantic-settings`. Reads from `.env`. Never hardcode secrets. Exposes: `OPENAI_API_KEY`, `DATABASE_URL`, `CHROMA_PERSIST_DIR`, `OPENAI_MODEL` (default `gpt-4o`), `EMBEDDING_MODEL` (default `text-embedding-3-small`), `RAG_TOP_K` (default `3`), `ENVIRONMENT` (`development` / `production`).

### `app/dependencies.py`
FastAPI dependency functions: `get_db()` yields a SQLAlchemy session; `get_rag_service()` returns the singleton RAG service; `get_analysis_service()` returns the singleton Analysis service.

### `app/routers/portfolio.py`
Single route: `POST /api/portfolio/analyze`. Receives `PortfolioRequest`, delegates entirely to `PortfolioService.analyze()`. Returns `PortfolioResponse`. Accepts optional `?format=pdf` query parameter — when set, calls `PDFService.generate()` and returns `StreamingResponse` with `Content-Type: application/pdf`.

### `app/routers/companies.py`
Two routes: `GET /api/companies` returns `list[CompanySchema]`; `GET /api/companies/{ticker}` returns `CompanyDetailSchema` with full financial history. Both are read-only DB queries — no LLM involvement.

### `app/services/portfolio_service.py`
Main orchestrator. Receives validated `PortfolioRequest`. Splits assets by type. Queries DB for STOCK companies. Fires concurrent per-STOCK analyses via `asyncio.gather`. Applies tone-of-voice trigger detection. Calls `AnalysisService.generate_portfolio_summary()`. Assembles and returns `PortfolioResponse`.

### `app/services/rag_service.py`
Wraps ChromaDB via a LangChain `Chroma` retriever. Exposes `retrieve(company_profile: str) -> list[BuffettCitation]`. Builds the semantic query string from company sector, ROE level, and debt profile. Returns top-K passages with year metadata.

### `app/services/analysis_service.py`
All GPT-4o interaction lives here. Two async methods: `analyze_stock(company, financials, citations) -> StockAnalysis` and `generate_portfolio_summary(assets, alerts) -> PortfolioSummary`. Both construct prompts from templates and call the OpenAI chat completions API. Structured output (JSON mode) is used so responses can be parsed directly into Pydantic models.

### `app/services/pdf_service.py`
Accepts a `PortfolioResponse` and an optional `WeasyPrint` context. Renders the `templates/report.html` Jinja2 template and uses WeasyPrint to produce a PDF `bytes` object. Returns bytes for the router to stream.

### `app/models/company.py` and `app/models/financial.py`
SQLAlchemy declarative ORM models matching the PostgreSQL schema exactly. `Company` has a `financials` relationship to `Financial`. All models import from `app.db.session.Base`.

### `app/schemas/portfolio.py`
Pydantic v2 schemas for the API contract:
- `AssetInput` — single asset in request (`ticker`, `type`, `percentage`)
- `PortfolioRequest` — list of `AssetInput` with validator asserting percentages sum to 100
- `BuffettCitation` — year, passage, relevance
- `StockAssetResponse` — full STOCK response shape
- `FIIAssetResponse` — minimal FII shape
- `TesourAssetResponse` — minimal TESOURO shape
- `PortfolioAlert` — type + message
- `PortfolioResponse` — top-level response

### `app/schemas/company.py`
`CompanySchema` and `CompanyDetailSchema` (with financial history list) for the companies endpoints.

### `app/rag/client.py`
Creates the ChromaDB `PersistentClient` once (singleton via module-level variable). Exposes `get_collection()` returning the `buffett_letters` collection. Used by `RAGService` and the ingestion script.

### `app/rag/ingest.py`
CLI script (run via `python -m app.rag.ingest`). Reads PDFs from `rag_data/pdfs/`. Extracts text via PyMuPDF. Chunks by paragraph targeting ~300 tokens. Tags each chunk with `year` (parsed from filename convention `YYYY_letter.pdf`), `letter_type: shareholder_letter`, and `topic` (empty string for v1 — topic tagging is future scope). Embeds via `text-embedding-3-small`. Stores in ChromaDB `buffett_letters` collection. Idempotent: skips already-ingested documents by checking document ID before insert.

### `app/db/session.py`
Creates the async SQLAlchemy engine from `Settings.DATABASE_URL`. Defines `Base` (declarative base) and `AsyncSessionLocal` factory. Exposes `get_db()` as an async generator for FastAPI dependency injection.

---

## API Contract

### POST /api/portfolio/analyze

**Request body:**
```json
{
  "assets": [
    {"ticker": "WEGE3",   "type": "STOCK",   "percentage": 35},
    {"ticker": "MXRF11",  "type": "FII",     "percentage": 15},
    {"ticker": "TESOURO", "type": "TESOURO", "percentage": 10},
    {"ticker": "PETR4",   "type": "STOCK",   "percentage": 40}
  ]
}
```

**Validation rules (enforced by Pydantic before the route handler runs):**
- `assets` must be non-empty
- Each `type` must be one of `STOCK`, `FII`, `TESOURO`
- `percentage` must be > 0 and <= 100
- Sum of all `percentage` values must equal 100 (tolerance: 0.01 to handle float rounding)

**Success response (200):**
```json
{
  "portfolio_grade": "B+",
  "portfolio_summary": "string",
  "portfolio_alerts": [
    {
      "type": "TESOURO_LOW",
      "message": "É muita coragem ter tão pouca renda fixa"
    }
  ],
  "assets": [
    {
      "ticker": "WEGE3",
      "company_name": "WEG S.A.",
      "sector": "Industrial",
      "type": "STOCK",
      "percentage": 35,
      "score": 9.2,
      "verdict": "APROVADO",
      "financials": {
        "roe": 28.5,
        "margem_liquida": 15.2,
        "cagr_lucro": 18.3,
        "divida_ebitda": 0.4
      },
      "buffett_verdict": "string",
      "buffett_citations": [
        {
          "year": 1992,
          "passage": "string",
          "relevance": "string"
        }
      ],
      "retail_adaptation_note": "string"
    },
    {
      "ticker": "MXRF11",
      "type": "FII",
      "percentage": 15,
      "verdict": "FII — análise detalhada em breve"
    },
    {
      "ticker": "TESOURO",
      "type": "TESOURO",
      "percentage": 10,
      "verdict": "Capital seguro"
    }
  ]
}
```

**Error responses:**
- `422 Unprocessable Entity` — validation failure (percentages don't sum to 100, unknown type, etc.)
- `404 Not Found` — STOCK ticker not found in database (body: `{"detail": "Ticker XXXX not found in database"}`)
- `503 Service Unavailable` — OpenAI API unreachable (body: `{"detail": "Analysis service temporarily unavailable"}`)
- `500 Internal Server Error` — unexpected error with correlation ID in response for log lookup

**Optional query parameter:** `?format=pdf`
When present, response is `application/pdf` instead of JSON, with `Content-Disposition: attachment; filename="warren_report.pdf"`.

---

### GET /api/companies

**Response (200):**
```json
[
  {
    "ticker": "WEGE3",
    "name": "WEG S.A.",
    "sector": "Industrial",
    "segment": "Máquinas e Equipamentos",
    "asset_type": "STOCK"
  }
]
```

---

### GET /api/companies/{ticker}

**Response (200):**
```json
{
  "ticker": "WEGE3",
  "name": "WEG S.A.",
  "sector": "Industrial",
  "segment": "Máquinas e Equipamentos",
  "asset_type": "STOCK",
  "financials": [
    {
      "year": 2024,
      "roe": 28.5,
      "lucro_liquido": 4200000000.00,
      "margem_liquida": 15.2,
      "receita_liquida": 27600000000.00,
      "divida_liquida": 1200000000.00,
      "ebitda": 5800000000.00,
      "divida_ebitda": 0.4,
      "market_cap": 180000000000.00,
      "p_l": 42.8,
      "cagr_lucro": 18.3
    }
  ]
}
```

**Error responses:**
- `404 Not Found` — ticker not in database

---

### GET /health

Returns `{"status": "ok"}` if the app is running. Does not check DB or ChromaDB.

### GET /ready

Checks DB connectivity and ChromaDB collection existence. Returns `{"status": "ok"}` if both pass, `503` with `{"status": "degraded", "detail": "..."}` otherwise. Used by Nginx/load balancer before routing traffic.

### GET /metrics

Prometheus-compatible metrics endpoint. Exposes RED metrics (rate, errors, duration) per endpoint. Middleware auto-instruments all routes.

---

## pyproject.toml additions needed

Add to `pyproject.toml` before implementing:

```toml
[project]
# Add these to the existing dependencies list:
# "pydantic-settings",
# "asyncpg",          # async PostgreSQL driver
# "greenlet",         # required by SQLAlchemy async
# "pytest",
# "pytest-asyncio",
# "pytest-cov",
# "pytest-mock",
# "httpx",            # already listed, used for async test client
# "aiosqlite",        # SQLite backend for unit test DB fixture

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "unit: pure logic tests, no I/O",
    "integration: requires real database and ChromaDB",
    "slow: calls OpenAI API (always mocked in CI)",
]

[tool.coverage.run]
source = ["app"]
omit = ["app/rag/ingest.py"]  # CLI script tested separately
```

---

## Alembic Setup

```bash
# Initialize (already done if migrations/ dir exists)
uv run alembic init migrations

# Create first migration after defining models
uv run alembic revision --autogenerate -m "create companies and financials tables"

# Apply
uv run alembic upgrade head

# Rollback one step
uv run alembic downgrade -1
```

The `alembic.ini` `sqlalchemy.url` should read from the environment variable, not be hardcoded.

---

## Key Conventions

- All service methods that touch the DB or call OpenAI are `async def`
- Route handlers are `async def`
- DB sessions are injected via `Depends(get_db)` — never instantiated directly in services
- ChromaDB client is a module-level singleton (initialized once at startup, safe because it's read-heavy)
- All logging uses `structlog` with `trace_id` injected by middleware — never use `print()`
- Error handling: services raise typed exceptions (`TickerNotFoundError`, `OpenAIUnavailableError`, `RAGEmptyResultError`); routers catch and map to HTTP status codes
- Never commit `.env` — it contains secrets
- `rag_data/` is in `.gitignore` — PDFs and ChromaDB files are not version-controlled
