# Warren Backend — Implementation Task List

**Rule:** TDD is mandatory. Every task that creates code must follow RED → GREEN → REFACTOR.  
**Reference files:** `CLAUDE.md` (how to run/test), `docs/ARCHITECTURE.md` (full design details).

---

## Agent assignment

| Block | Agent |
|-------|-------|
| [A] Infrastructure & Config](#a-infrastructure--config) | Claude |
| [B] Database Layer](#b-database-layer) | Claude |
| [C] Pydantic Schemas](#c-pydantic-schemas) | Claude |
| [D] Exceptions](#d-exceptions) | Claude |
| [E] Services — Non-AI](#e-services--non-ai) | Claude |
| [F] Routers & App Factory](#f-routers--app-factory) | Claude |
| [G] Observability](#g-observability) | Claude |
| [H] Non-AI Tests](#h-non-ai-tests) | Claude |
| [I] RAG Client & Ingestion](#i-rag-client--ingestion) | AI Agent |
| [J] RAG Service](#j-rag-service) | AI Agent |
| [K] Analysis Service — GPT-4o](#k-analysis-service--gpt-4o) | AI Agent |
| [L] AI Service Dependencies](#l-ai-service-dependencies) | AI Agent |
| [M] AI Tests](#m-ai-tests) | AI Agent |

---

## [A] Infrastructure & Config

### A1 — Update `pyproject.toml`
Add missing dependencies to the existing file (do not replace existing entries):

```
pydantic-settings
asyncpg
greenlet
aiosqlite
structlog
prometheus-fastapi-instrumentator
pytest
pytest-asyncio
pytest-cov
pytest-mock
```

Add pytest config block:
```toml
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
omit = ["app/rag/ingest.py"]
```

- [ ] Done

---

### A2 — Create folder structure

Create all `__init__.py` files and empty directories:

```
app/
  routers/__init__.py
  services/__init__.py
  models/__init__.py
  schemas/__init__.py
  rag/__init__.py
  db/__init__.py
tests/
  routers/
  services/
  schemas/
  rag/
  __init__.py (in each subfolder)
templates/
rag_data/
  pdfs/.gitkeep
  chroma/.gitkeep
migrations/versions/
```

- [ ] Done

---

### A3 — Create `.gitignore` entries

Add to (or create) `.gitignore`:
```
.env
rag_data/chroma/
rag_data/pdfs/
__pycache__/
*.pyc
.pytest_cache/
htmlcov/
.coverage
```

- [ ] Done

---

### A4 — Create `app/config.py`

`Settings` class using `pydantic-settings`. Full spec in `ARCHITECTURE.md §10`.

Fields:
- `OPENAI_API_KEY: str` — required
- `DATABASE_URL: str` — required
- `CHROMA_PERSIST_DIR: str = "./rag_data"`
- `OPENAI_MODEL: str = "gpt-4o"`
- `EMBEDDING_MODEL: str = "text-embedding-3-small"`
- `RAG_TOP_K: int = 3`
- `OPENAI_TIMEOUT_SECONDS: int = 30`
- `ENVIRONMENT: str = "development"`
- `CORS_ORIGINS: str = "http://localhost:3000"`
- `LOG_LEVEL: str = "INFO"`

Module-level singleton: `settings = Settings()`

**TDD:** Write `tests/test_config.py` first. Test that Settings reads from env vars, that missing required fields raise `ValidationError`, and that defaults apply.

- [ ] Done

---

## [B] Database Layer

> Complete A1–A4 before starting B.

### B1 — Create `app/db/session.py`

Async SQLAlchemy engine and session factory. Full spec in `ARCHITECTURE.md §4`.

- `Base = declarative_base()`
- `engine = create_async_engine(settings.DATABASE_URL, ...)`
- `AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)`
- `async def get_db()` — async generator for FastAPI `Depends`

**TDD:** Write `tests/db/test_session.py` first. Test that `get_db()` yields a session and closes it.

- [ ] Done

---

### B2 — Create `app/models/company.py`

SQLAlchemy `Company` ORM model. Full spec in `ARCHITECTURE.md §4`:
- Columns: `id`, `ticker` (unique, indexed), `name`, `sector`, `segment`, `asset_type`
- Relationship: `financials` → `Financial`, ordered by `year DESC`

- [ ] Done

---

### B3 — Create `app/models/financial.py`

SQLAlchemy `Financial` ORM model. Full spec in `ARCHITECTURE.md §4`:
- Columns: `id`, `company_id` (FK), `year`, `roe`, `lucro_liquido`, `margem_liquida`, `receita_liquida`, `divida_liquida`, `ebitda`, `divida_ebitda`, `market_cap`, `p_l`, `cagr_lucro`
- Unique constraint: `(company_id, year)`
- Relationship back to `Company`

- [ ] Done

---

### B4 — Alembic setup

```bash
uv run alembic init migrations
```

Edit `migrations/env.py`:
- Import `Base` from `app.db.session`
- Set `target_metadata = Base.metadata`
- Read `DATABASE_URL` from environment (not hardcoded in `alembic.ini`)

Edit `alembic.ini`:
- Set `sqlalchemy.url = %(DATABASE_URL)s` — reads from env at runtime

- [ ] Done

---

### B5 — First Alembic migration

```bash
uv run alembic revision --autogenerate -m "create companies and financials tables"
```

After generating, manually add the extra indexes to the migration file:
```sql
op.create_index("ix_financials_company_year", "financials", ["company_id", "year"])
op.create_index("ix_companies_asset_type", "companies", ["asset_type"])
```

Verify: `uv run alembic upgrade head` against a local PostgreSQL instance.

- [ ] Done

---

## [C] Pydantic Schemas

> Complete A4 before starting C.

### C1 — Create `app/schemas/portfolio.py`

Full spec in `ARCHITECTURE.md §5`. Implement in this order:

1. `AssetType` enum (`STOCK`, `FII`, `TESOURO`)
2. `AssetInput` — with `ticker` max_length=10, `percentage` gt=0 le=100
3. `PortfolioRequest` — with `@model_validator` asserting percentages sum to 100 (tolerance 0.01)
4. `BuffettCitation` — year, passage, relevance
5. `FinancialSnapshot` — roe, margem_liquida, cagr_lucro, divida_ebitda (all `float | None`)
6. `StockAssetResponse` — full STOCK shape
7. `FIIAssetResponse` — with default verdict `"FII — análise detalhada em breve"`
8. `TesouroAssetResponse` — with default verdict `"Capital seguro"`
9. `AssetResponse` — discriminated union with `Field(discriminator="type")`
10. `AlertType` enum
11. `PortfolioAlert`
12. `PortfolioResponse`

**TDD:** Write `tests/schemas/test_portfolio_schemas.py` first. Test cases:
- Valid portfolio with all three asset types
- Percentages summing to 99.5 → `ValidationError`
- Percentages summing to 100.005 → passes (within tolerance)
- Empty assets list → `ValidationError`
- `percentage=0` → `ValidationError`
- `type="UNKNOWN"` → `ValidationError`

- [ ] Done

---

### C2 — Create `app/schemas/company.py`

Full spec in `ARCHITECTURE.md §5`:

1. `CompanySchema` — ticker, name, sector, segment, asset_type; `model_config = ConfigDict(from_attributes=True)`
2. `FinancialHistoryItem` — all columns from `Financial` model as `float | None`; `from_attributes=True`
3. `CompanyDetailSchema(CompanySchema)` — adds `financials: list[FinancialHistoryItem]`

- [ ] Done

---

## [D] Exceptions

> Can be done any time after A4.

### D1 — Create `app/exceptions.py`

Full spec in `ARCHITECTURE.md §9`:

```python
class WarrenBaseError(Exception): ...
class TickerNotFoundError(WarrenBaseError): ...  # stores ticker attribute
class OpenAIUnavailableError(WarrenBaseError): ...
class RAGEmptyResultError(WarrenBaseError): ...   # not raised in v1
class PDFGenerationError(WarrenBaseError): ...
```

**TDD:** Write `tests/test_exceptions.py` first. Test that `TickerNotFoundError("XXXX")` stores `.ticker` and has the right `str()`.

- [ ] Done

---

## [E] Services — Non-AI

> Complete B, C, D before starting E.

### E1 — Create `app/services/portfolio_service.py` (skeleton)

The orchestrator. At this stage, implement everything **except** the actual AI calls — those come from `RAGService` and `AnalysisService` (built by the AI agent). Use constructor injection for AI services so tests can mock them.

Implement:
1. `detect_alerts(assets: list[AssetInput]) -> list[PortfolioAlert]` — pure function, no I/O. Full logic in `ARCHITECTURE.md §7`:
   - `TESOURO_ZERO` if tesouro_pct == 0
   - `TESOURO_LOW` if tesouro_pct > 0 and < 5
   - `SINGLE_STOCK_100` if any single stock >= 99.9%
   - `COMMODITY_HEAVY` if commodity tickers sum > 40% (hardcoded set for now per design)
   - `OVER_CONCENTRATED` if top-2 percentages sum > 80%

2. `PortfolioService.__init__(self, rag_service, analysis_service)` — injected dependencies

3. `async PortfolioService.analyze(request: PortfolioRequest, db: AsyncSession) -> PortfolioResponse`:
   - Split assets into stocks/fiis/tesouros
   - Query DB for each stock (raises `TickerNotFoundError` if not found)
   - Call `asyncio.gather` over stock analyses (delegates to injected `analysis_service`)
   - Call `detect_alerts`
   - Call `analysis_service.generate_portfolio_summary`
   - Assemble `PortfolioResponse`
   - Handle partial degradation: if one stock's gather task raises, return degraded `StockAssetResponse`

**TDD:** Write `tests/services/test_portfolio_service.py` first. All AI services mocked. Test cases:
- `detect_alerts` for every trigger condition independently
- `detect_alerts` multiple alerts at once
- `analyze` raises `TickerNotFoundError` for unknown ticker
- `analyze` returns correct shape with mocked AI services
- `analyze` partial degradation when one mocked AI call raises

- [ ] Done

---

### E2 — Create `app/services/pdf_service.py`

Full spec in `ARCHITECTURE.md §8`.

```python
class PDFService:
    def generate(self, portfolio_response: PortfolioResponse) -> bytes:
        ...
```

- Load `templates/report.html` via `jinja2.Environment(loader=FileSystemLoader("templates"))`
- Render with `portfolio_response.model_dump()` as context
- Call `weasyprint.HTML(string=html).write_pdf()`
- Raise `PDFGenerationError` on any WeasyPrint exception

**TDD:** Write `tests/services/test_pdf_service.py` first. Mock WeasyPrint. Test:
- Returns `bytes` for valid `PortfolioResponse`
- Raises `PDFGenerationError` when WeasyPrint raises

- [ ] Done

---

### E3 — Create `templates/report.html`

Jinja2 template for PDF export. Full spec in `ARCHITECTURE.md §8`.

Sections:
1. `<style>` block — all CSS inline (WeasyPrint has no external stylesheet support at runtime)
2. Header — app name, analysis date, disclaimer text
3. Portfolio overview — grade badge (colored by grade), summary text, alerts list
4. Asset cards loop:
   - STOCK card: name, ticker, sector, score bar, verdict badge (colored), financials table, Buffett verdict, citations block, retail note
   - FII card: ticker, percentage, fixed verdict pill
   - TESOURO card: ticker, percentage, "Capital seguro" badge
5. `@page` CSS rule with legal disclaimer in footer on every page

Verdict colors: APROVADO → `#22c55e`, ATENÇÃO → `#f59e0b`, REPROVADO → `#ef4444`  
Grade colors: A/A- → green, B+/B/B- → blue, C+/C/C- → amber, D/F → red

Legal disclaimer footer text:
> "Esta análise é meramente informativa e não constitui recomendação de investimento. Consulte um assessor de investimentos certificado. Não nos responsabilizamos por decisões de investimento baseadas neste relatório."

- [ ] Done

---

## [F] Routers & App Factory

> Complete B, C, D, E before starting F.

### F1 — Create `app/routers/companies.py`

Two routes — read-only DB queries, no AI involved:

1. `GET /companies` → `list[CompanySchema]`
   - Query all companies ordered by ticker
   - Returns 200 with list

2. `GET /companies/{ticker}` → `CompanyDetailSchema`
   - Query company by ticker with all financials (ordered by year DESC)
   - Returns 404 if not found

**TDD:** Write `tests/routers/test_companies.py` first. Use in-memory SQLite via the `db_session` fixture. Seed 2–3 companies. Test:
- GET /companies returns all companies
- GET /companies/{ticker} returns company with financials
- GET /companies/UNKNOWN → 404

- [ ] Done

---

### F2 — Create `app/routers/portfolio.py`

One route:

`POST /portfolio/analyze` (prefix `/api` applied in main.py)
- Receives `PortfolioRequest`
- Injects `db = Depends(get_db)`, `portfolio_service = Depends(get_portfolio_service)`
- Calls `portfolio_service.analyze(request, db)`
- Optional `?format=pdf` query param: if `format == "pdf"`, calls `PDFService.generate()` and returns `StreamingResponse`
- Returns `PortfolioResponse` JSON otherwise

**TDD:** Write `tests/routers/test_portfolio.py` first. `PortfolioService` fully mocked. Test:
- Valid request → 200 with correct response shape
- Percentages don't sum to 100 → 422
- `PortfolioService` raises `TickerNotFoundError` → 404
- `PortfolioService` raises `OpenAIUnavailableError` → 503
- `?format=pdf` returns `application/pdf` content type

- [ ] Done

---

### F3 — Create `app/dependencies.py`

FastAPI dependency functions:

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]: ...

def get_rag_service(request: Request) -> RAGService:
    return request.app.state.rag_service

def get_analysis_service() -> AnalysisService:
    # Returns module-level singleton
    ...

def get_portfolio_service(
    rag_service = Depends(get_rag_service),
    analysis_service = Depends(get_analysis_service),
) -> PortfolioService:
    return PortfolioService(rag_service, analysis_service)
```

Note: `get_rag_service` reads from `app.state` (set in lifespan). The AI agent fills in the concrete `RAGService` implementation; this file just wires it.

- [ ] Done

---

### F4 — Create `app/main.py`

FastAPI app factory. Full spec in `CLAUDE.md §Module Responsibilities`:

1. `lifespan` context manager:
   - On startup: initialize ChromaDB client → store as `app.state.chroma_client`; create `RAGService(chroma_client)` → store as `app.state.rag_service`
   - On shutdown: dispose SQLAlchemy engine
2. `app = FastAPI(lifespan=lifespan, title="Warren Backend", version="0.1.0")`
3. `CORSMiddleware` — origins from `settings.CORS_ORIGINS.split(",")`, methods `["GET", "POST"]`, `allow_credentials=False`
4. Request ID middleware — generates UUID4 per request, stores in `ContextVar`, injects into structlog context
5. Register exception handlers: `TickerNotFoundError → 404`, `OpenAIUnavailableError → 503`, `PDFGenerationError → 500`
6. Include routers: `app.include_router(portfolio_router, prefix="/api")` and `app.include_router(companies_router, prefix="/api")`
7. `GET /health` → `{"status": "ok"}`
8. `GET /ready` → checks DB (`SELECT 1`) and ChromaDB collection; returns 200 or 503
9. Prometheus: `Instrumentator().instrument(app).expose(app)`

**TDD:** Write `tests/test_main.py` first. Test health endpoint, CORS headers on OPTIONS, 404 on unknown route.

- [ ] Done

---

## [G] Observability

> Complete F4 before starting G.

### G1 — Configure `structlog`

In `app/main.py` or a separate `app/logging.py`:
- Configure `structlog` to output JSON in `ENVIRONMENT=production`, colored console in `development`
- Every log entry must include `trace_id` (from `ContextVar`), `service="warren-backend"`, `environment`
- Add processor to redact fields named `api_key`, `secret`, `password`

Replace any `print()` calls in the codebase with `structlog.get_logger().info(...)`.

- [ ] Done

---

### G2 — Prometheus custom metrics

In `app/services/portfolio_service.py` (or a `app/metrics.py` module):

```python
from prometheus_client import Counter, Histogram

openai_calls_total = Counter("warren_openai_calls_total", "...", ["call_type"])
openai_duration_seconds = Histogram("warren_openai_duration_seconds", "...", ["call_type"])
rag_results_count = Histogram("warren_rag_results_total", "...")
```

Increment `openai_calls_total` and observe `openai_duration_seconds` in `AnalysisService` calls (or wrap in `PortfolioService`). Observe `rag_results_count` in `RAGService`.

- [ ] Done

---

## [H] Non-AI Tests

> Complete A–G before writing tests (TDD means tests come first per task, but this tracks the overall test suite health).

### H1 — Create `tests/conftest.py`

Mandatory shared fixtures (full spec in `CLAUDE.md §How to Test`):

```python
@pytest.fixture
async def db_session():
    # In-memory SQLite (aiosqlite) for unit tests
    # Creates all tables via Base.metadata.create_all
    ...

@pytest.fixture
def chroma_client():
    # Ephemeral in-memory ChromaDB client (not PersistentClient)
    ...

@pytest.fixture
def chroma_with_data(chroma_client):
    # Seeds 3 fake Buffett passages into the in-memory client
    ...

@pytest.fixture
async def async_client(db_session, chroma_with_data):
    # AsyncClient (httpx) wrapping the FastAPI app
    # Overrides get_db dependency with db_session fixture
    ...
```

- [ ] Done

---

### H2 — Verify full test suite passes

```bash
uv run pytest -m "not integration and not slow" --cov=app --cov-report=term-missing
```

All non-AI tests (schemas, db, services with mocked AI, routers with mocked services) must pass.  
Target: ≥ 80% coverage on non-AI modules.

- [ ] Done

---

## [I] RAG Client & Ingestion

> **AI Agent starts here.** Complete A–D (at minimum A1, A4, D1) before starting I.  
> Read `ARCHITECTURE.md §3` for full ChromaDB spec before implementing.

### I1 — Create `app/rag/client.py`

ChromaDB singleton. Full spec in `ARCHITECTURE.md §3`:

- `chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)`
- Module-level singleton: created once, reused
- `get_collection() -> chromadb.Collection` — returns or creates the `buffett_letters` collection
- Embedding function: `langchain_openai.OpenAIEmbeddings(model=settings.EMBEDDING_MODEL)`

**TDD:** Write test using in-memory ChromaDB client (`chromadb.EphemeralClient()`). Test that `get_collection()` returns a collection named `buffett_letters`.

- [ ] Done

---

### I2 — Create `app/rag/ingest.py`

CLI ingestion script. Full spec in `ARCHITECTURE.md §3`:

```bash
uv run python -m app.rag.ingest
```

Logic:
1. Scan `rag_data/pdfs/` for files matching `YYYY_letter.pdf`
2. For each file: extract year from filename
3. Extract text via `fitz.open()` (PyMuPDF)
4. Split by `\n\n`, then apply `RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)` for paragraphs > 400 tokens
5. Filter chunks < 100 chars
6. Assign doc ID: `"{year}_letter_chunk_{index:03d}"`
7. Idempotency: if any doc ID with `source_file = "YYYY_letter.pdf"` already exists in collection → skip entire file (see Suggestion S11 in ARCHITECTURE.md)
8. Embed all new chunks via OpenAI `text-embedding-3-small`
9. Insert into `buffett_letters` collection
10. Log progress per PDF via structlog

Chunk metadata schema:
```python
{
    "year": int,
    "letter_type": "shareholder_letter",
    "topic": "",  # empty in v1
    "source_file": "YYYY_letter.pdf"
}
```

**TDD:** Write `tests/rag/test_ingest.py` using an in-memory ChromaDB. Mock PyMuPDF and OpenAI. Test:
- Parses year from filename correctly
- Skips non-matching filenames with a warning log
- Chunks are stored with correct metadata
- Second run on same file is idempotent (no duplicate inserts)

- [ ] Done

---

## [J] RAG Service

> Complete I1 before starting J.  
> Read `ARCHITECTURE.md §3` for full retrieval query spec.

### J1 — Create `app/services/rag_service.py`

Single public method: `retrieve(ticker, sector, roe, divida_ebitda) -> list[BuffettCitation]`

Logic (full spec in `ARCHITECTURE.md §3`):
1. Build semantic query:
   ```python
   debt_level = "low debt" if divida_ebitda < 1.0 else "moderate debt" if divida_ebitda < 3.0 else "high debt"
   SECTOR_MOAT_HINTS = {
       "Industrial": "durable competitive advantage, pricing power",
       "Financeiro": "return on equity, capital allocation",
       "Energia": "commodity exposure, capital intensity",
       "Consumo": "brand moat, consumer loyalty",
       "Tecnologia": "switching costs, scalability",
   }
   moat_hint = SECTOR_MOAT_HINTS.get(sector, "competitive position")
   query = f"Brazilian {sector} company, ROE {roe:.0f}%, {debt_level}, {moat_hint}"
   ```
2. Call `Chroma.similarity_search(query, k=settings.RAG_TOP_K)` on `buffett_letters` collection
3. Map `Document` objects to `BuffettCitation(year=doc.metadata["year"], passage=doc.page_content, relevance="")`
4. On ChromaDB error: log with structlog, return `[]` — do NOT raise
5. On empty results: return `[]` — do NOT raise

**TDD:** Write `tests/services/test_rag_service.py`. Use `chroma_with_data` fixture (3 seeded passages). Test:
- Returns list of `BuffettCitation` for a valid query
- Returns `[]` when collection is empty
- Returns `[]` (and logs) when ChromaDB raises
- Query string is built correctly for each debt level and known sectors

- [ ] Done

---

## [K] Analysis Service — GPT-4o

> Complete C (schemas) and D (exceptions) before starting K.  
> Read `ARCHITECTURE.md §6` for full prompt templates before writing any code.

### K1 — Create `app/services/analysis_service.py`

All GPT-4o interaction. Full spec in `ARCHITECTURE.md §6`.

```python
class AnalysisService:
    def __init__(self, api_key: str, model: str, timeout: int): ...

    async def analyze_stock(
        self,
        company: Company,
        financials: Financial,
        citations: list[BuffettCitation],
    ) -> StockAnalysis:
        ...

    async def generate_portfolio_summary(
        self,
        assets: list[AssetResponse],
        alerts: list[PortfolioAlert],
    ) -> PortfolioSummary:
        ...
```

`StockAnalysis` is an internal Pydantic model (not exposed in API):
```python
class StockAnalysis(BaseModel):
    score: float
    verdict: str
    buffett_verdict: str
    buffett_citations: list[BuffettCitation]
    retail_adaptation_note: str
```

`PortfolioSummary`:
```python
class PortfolioSummary(BaseModel):
    portfolio_grade: str
    portfolio_summary: str
```

Both methods:
- Use `openai.AsyncOpenAI(api_key=..., timeout=...)` 
- Pass `response_format={"type": "json_object"}` on every call
- Parse JSON response into the relevant Pydantic model
- Raise `OpenAIUnavailableError` on `openai.APIConnectionError`, `openai.APITimeoutError`, or JSON parse failure

**Prompt templates** (copy exactly from `ARCHITECTURE.md §6`):
- Per-stock system prompt: enforces no directive language, Brazilian Portuguese, retail context, scoring rubric, expected JSON output shape
- Per-stock user prompt: company name, ticker, sector, latest financials, formatted citations
- Portfolio summary system prompt: grading scale A–F
- Portfolio summary user prompt: all assets, detected alerts

**TDD:** Write `tests/services/test_analysis_service.py`. Mock `openai.AsyncOpenAI`. Test:
- `analyze_stock` parses valid JSON response into `StockAnalysis`
- `analyze_stock` raises `OpenAIUnavailableError` on `APIConnectionError`
- `analyze_stock` raises `OpenAIUnavailableError` on invalid JSON response
- `generate_portfolio_summary` parses valid JSON into `PortfolioSummary`
- Prompt contains no directive language ("recomendamos", "você deve", etc.) — assert on the constructed prompt string

- [ ] Done

---

## [L] AI Service Dependencies

> Complete I1, J1, K1 before starting L.

### L1 — Wire AI services into `app/dependencies.py`

Fill in the AI service dependency functions (scaffolded by Claude in F3):

```python
def get_rag_service(request: Request) -> RAGService:
    return request.app.state.rag_service  # set by lifespan

def get_analysis_service() -> AnalysisService:
    return _analysis_service_singleton  # module-level, initialized on import
```

Update `app/main.py` lifespan to:
1. Create `RAGService(chroma_client)` on startup, store as `app.state.rag_service`
2. Create `AnalysisService(settings.OPENAI_API_KEY, settings.OPENAI_MODEL, settings.OPENAI_TIMEOUT_SECONDS)` as a module-level singleton in `dependencies.py`

- [ ] Done

---

## [M] AI Tests

> Complete I, J, K, L before running M.

### M1 — Integration smoke test

```bash
uv run pytest -m integration
```

Requires:
- Local PostgreSQL with at least 2 seeded companies (WEGE3, PETR4)
- ChromaDB populated via `uv run python -m app.rag.ingest` (with at least 1 PDF)
- `.env` with valid `OPENAI_API_KEY`

Test file: `tests/integration/test_analyze_endpoint.py`

Test case: POST `/api/portfolio/analyze` with `[WEGE3 (STOCK, 60%), TESOURO (TESOURO, 40%)]` → 200, response shape matches `PortfolioResponse`, WEGE3 has a score and citations, TESOURO has fixed verdict.

- [ ] Done

---

### M2 — Full test suite passing

```bash
uv run pytest --cov=app --cov-report=term-missing
```

All tests (unit + integration, excluding `slow` marker) must pass.  
Target: ≥ 80% overall coverage.

- [ ] Done

---

## Dependency order summary

```
A1 → A2 → A3 → A4
                ↓
          B1 → B2 → B3 → B4 → B5
          C1 → C2
          D1
                ↓
          E1 → E2 → E3
                ↓
          F1 → F2 → F3 → F4
                ↓
          G1 → G2
          H1 → H2

(Parallel, after A1+A4+D1)
          I1 → I2
          I1 → J1
          C+D → K1
          I1+J1+K1 → L1 → M1 → M2
```

---

## Quick reference — what each agent owns

### Claude agent owns (A–H)
`pyproject.toml`, folder structure, `.gitignore`, `app/config.py`, `app/db/session.py`, `app/models/`, `migrations/`, `app/schemas/`, `app/exceptions.py`, `app/services/portfolio_service.py` (orchestration + alerts), `app/services/pdf_service.py`, `templates/report.html`, `app/routers/`, `app/main.py`, `app/dependencies.py` (scaffold), observability config, all non-AI tests.

### AI agent owns (I–M)
`app/rag/client.py`, `app/rag/ingest.py`, `app/services/rag_service.py`, `app/services/analysis_service.py`, `app/dependencies.py` (AI service wiring), all AI-related tests.
