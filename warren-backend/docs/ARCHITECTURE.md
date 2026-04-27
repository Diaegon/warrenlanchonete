# Warren Backend — Architecture Document

**Date:** 2026-04-27
**Status:** Approved
**Scope:** `warren-backend` FastAPI service only

---

## Table of Contents

1. [Module Responsibilities](#1-module-responsibilities)
2. [Async Strategy](#2-async-strategy)
3. [ChromaDB Integration](#3-chromadb-integration)
4. [PostgreSQL Models](#4-postgresql-models)
5. [Pydantic Schemas](#5-pydantic-schemas)
6. [GPT-4o Prompt Design](#6-gpt-4o-prompt-design)
7. [Tone of Voice Trigger System](#7-tone-of-voice-trigger-system)
8. [PDF Export](#8-pdf-export)
9. [Error Handling Map](#9-error-handling-map)
10. [Config](#10-config)
11. [Observability](#11-observability)
12. [Security](#12-security)
13. [Suggestions and Gaps](#13-suggestions-and-gaps)

---

## 1. Module Responsibilities

### Layered Architecture

```
HTTP Request
     │
     ▼
┌─────────────────┐
│   Routers       │  Input validation (Pydantic), HTTP concerns, status codes
│  (app/routers/) │  No business logic here
└────────┬────────┘
         │ calls
         ▼
┌─────────────────┐
│   Services      │  All business logic lives here
│ (app/services/) │  Services depend on: DB session, RAG client, OpenAI client
└────────┬────────┘
         │ reads
    ┌────┴────────────────┐
    │                     │
    ▼                     ▼
┌─────────┐        ┌──────────────┐
│   ORM   │        │  RAG client  │
│ models  │        │  (ChromaDB)  │
└─────────┘        └──────────────┘
    │
    ▼
PostgreSQL
```

### Service Dependency Graph

```
PortfolioService
  ├── RAGService          (ChromaDB retrieval per STOCK)
  ├── AnalysisService     (GPT-4o per-asset + summary)
  └── PDFService          (optional, only when ?format=pdf)

AnalysisService
  └── openai.AsyncOpenAI  (chat completions, JSON mode)

RAGService
  └── langchain Chroma    (wraps ChromaDB PersistentClient)
```

### `PortfolioService` — Orchestrator

This is the only service the router calls. Its `analyze(request, db)` method:

1. Splits `request.assets` into three buckets: `stocks`, `fiis`, `tesouros`
2. For each stock ticker, queries `Company` + latest `Financial` from PostgreSQL — raises `TickerNotFoundError` if missing
3. Fires `asyncio.gather(*[_analyze_single_stock(c, f, db) for c, f in stock_pairs])` for concurrent per-stock analysis
4. Detects tone-of-voice triggers from the assembled results (see section 7)
5. Calls `AnalysisService.generate_portfolio_summary()` with all per-asset results and detected alerts
6. Assembles `PortfolioResponse` and returns it

The service does NOT call OpenAI directly — that is delegated entirely to `AnalysisService`.

### `RAGService` — ChromaDB Retrieval

Single public method: `retrieve(ticker: str, sector: str, roe: float, divida_ebitda: float) -> list[BuffettCitation]`

Internally:
- Builds semantic query string: `"Brazilian {sector} company, ROE {roe:.0f}%, debt/EBITDA {debt_level}, {moat_hint}"`
  - `debt_level` is mapped: < 1.0 → "low debt", 1.0–3.0 → "moderate debt", > 3.0 → "high debt"
  - `moat_hint` is mapped from sector: e.g., "Industrial" → "durable competitive advantage"
- Calls LangChain `Chroma.similarity_search(query, k=RAG_TOP_K)` on the `buffett_letters` collection
- Maps returned `Document` objects to `BuffettCitation(year=doc.metadata["year"], passage=doc.page_content, relevance="")`
  - The `relevance` field is filled in by GPT-4o in the analysis prompt, not here
- Returns empty list if ChromaDB has no results (does NOT raise — the analysis prompt handles missing citations gracefully)

### `AnalysisService` — GPT-4o

Two async methods:

**`analyze_stock(company, financials, citations) -> StockAnalysis`**
- Constructs per-asset prompt (see section 6)
- Calls `openai.AsyncOpenAI().chat.completions.create()` with `response_format={"type": "json_object"}`
- Parses JSON response into `StockAnalysis` Pydantic model
- Raises `OpenAIUnavailableError` on `openai.APIConnectionError` or `openai.APITimeoutError`

**`generate_portfolio_summary(assets, alerts) -> PortfolioSummary`**
- Constructs portfolio summary prompt (see section 6)
- Same OpenAI call pattern
- Returns `PortfolioSummary(grade, summary_text)`

### `PDFService` — PDF Generation

Method: `generate(portfolio_response: PortfolioResponse) -> bytes`

- Renders `templates/report.html` using `jinja2.Environment`
- Passes the full `PortfolioResponse` as template context (use `.model_dump()` for dict conversion)
- Calls `weasyprint.HTML(string=html).write_pdf()`
- Returns raw bytes — the router wraps in `StreamingResponse`

This is CPU-bound, not async. The router calls it synchronously after the async analysis pipeline completes. For v1 this is acceptable given low expected concurrency on a VPS.

---

## 2. Async Strategy

### Concurrency Model

The backend uses Python's `asyncio` throughout. Key decisions:

**DB queries:** Use `sqlalchemy.ext.asyncio` (`AsyncSession`) with `asyncpg` as the driver. All ORM queries are `await session.execute(...)`. This allows DB I/O to yield the event loop instead of blocking.

**OpenAI calls:** `openai.AsyncOpenAI` client. All `chat.completions.create()` calls are awaited.

**Per-stock parallelism:** Multiple stocks in a portfolio are analyzed concurrently using `asyncio.gather`. Each `_analyze_single_stock` coroutine performs: DB query (async) + ChromaDB retrieval (sync, but fast) + GPT-4o call (async). This means a 4-stock portfolio fires 4 GPT-4o calls concurrently rather than sequentially — latency is bounded by the slowest single stock, not the sum.

Example: portfolio with WEGE3, PETR4, VALE3, ITUB4 → 4 concurrent GPT-4o calls → ~2-3s total instead of ~8-12s sequential.

**ChromaDB retrieval:** ChromaDB's Python client is synchronous. Since retrieval is fast (sub-100ms, local disk), it is called directly without `run_in_executor`. If profiling reveals this becomes a bottleneck, wrap with `asyncio.get_event_loop().run_in_executor(None, ...)`.

**PDF generation:** WeasyPrint is CPU-bound synchronous. For v1, call directly. If PDF generation blocks the event loop for > 500ms under load, wrap with `run_in_executor` using a `ThreadPoolExecutor`.

### Concurrency Diagram

```
POST /analyze (arrives)
      │
      ├── DB: get WEGE3 company + financials   ──┐
      ├── DB: get PETR4 company + financials   ──┤ asyncio.gather
      │                                          │ (concurrent)
      ├── RAG: retrieve for WEGE3              ──┤
      ├── RAG: retrieve for PETR4              ──┤
      │                                          │
      ├── GPT-4o: analyze WEGE3                ──┤
      └── GPT-4o: analyze PETR4                ──┘
                                                 │
                                    all results assembled
                                                 │
                                    GPT-4o: portfolio summary
                                                 │
                                         return response
```

Note: In the actual implementation, each stock's DB query + RAG + GPT call are sequential within that stock's coroutine, but all stocks run in parallel across coroutines.

### Timeout Strategy

- Per-stock OpenAI call timeout: 30 seconds (configurable via `OPENAI_TIMEOUT_SECONDS` in Settings)
- Portfolio summary OpenAI call timeout: 45 seconds
- DB query timeout: set via `pool_timeout` in engine creation
- If any per-stock call times out: that asset gets `verdict: "Análise indisponível no momento"` and the rest of the portfolio proceeds normally (partial degradation, not full failure)

---

## 3. ChromaDB Integration

### Collection Setup

- Collection name: `buffett_letters`
- Client: `chromadb.PersistentClient(path=Settings.CHROMA_PERSIST_DIR)`
- Embedding function: LangChain's `OpenAIEmbeddings(model="text-embedding-3-small")`
- Distance metric: cosine (ChromaDB default)

The client is created once at application startup (inside the `lifespan` context manager in `app/main.py`) and stored as an application state attribute (`app.state.chroma_client`). The `get_rag_service()` dependency reads from `app.state`.

### Document Schema

Each document stored in ChromaDB:

```python
{
    "id": "1992_letter_chunk_042",      # "{year}_letter_chunk_{index:03d}"
    "document": "...",                   # raw text of the chunk (~300 tokens)
    "metadata": {
        "year": 1992,                    # int — the letter year
        "letter_type": "shareholder_letter",
        "topic": "",                     # empty in v1; future: "moat,pricing_power"
        "source_file": "1992_letter.pdf"
    }
}
```

### PDF Naming Convention

PDFs must be placed in `rag_data/pdfs/` with the naming pattern: `YYYY_letter.pdf` (e.g., `1992_letter.pdf`). The ingestion script parses the year from the filename prefix. Files that do not match this pattern are skipped with a warning log.

### Ingestion Script Design (`app/rag/ingest.py`)

```
for each PDF in rag_data/pdfs/:
    1. Extract year from filename
    2. Extract text via fitz.open() (PyMuPDF)
    3. Split text into paragraphs (split on "\n\n")
    4. For paragraphs > 400 tokens: split further using LangChain RecursiveCharacterTextSplitter
       (chunk_size=1200 chars, chunk_overlap=150 chars)
    5. Filter out chunks < 100 chars (page numbers, headers, etc.)
    6. Assign document ID: "{year}_letter_chunk_{index:03d}"
    7. Check if ID already exists in collection (idempotent)
    8. If new: embed + store
    9. Log progress per PDF

Total expected documents: ~800-1200 chunks across ~40 letters (1977-2023)
```

### Retrieval Query Construction

The semantic query is built in `RAGService.retrieve()` to be as specific as possible:

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

### Year-Based Temporal Filtering

The `retrieve()` method accepts an optional `min_year: int` parameter. If provided, a ChromaDB `where` filter is applied: `{"year": {"$gte": min_year}}`. For v1, this is not used. Future use: filter out pre-1990 letters when the context is about modern technology companies where advice from the 1970s may be less relevant.

---

## 4. PostgreSQL Models

### `Company` Model (`app/models/company.py`)

```python
class Company(Base):
    __tablename__ = "companies"

    id         = Column(Integer, primary_key=True)
    ticker     = Column(String(10), unique=True, nullable=False, index=True)
    name       = Column(String(200), nullable=False)
    sector     = Column(String(100))
    segment    = Column(String(100))
    asset_type = Column(String(10), nullable=False)  # 'STOCK' or 'FII'

    financials = relationship("Financial", back_populates="company",
                              order_by="Financial.year.desc()")
```

### `Financial` Model (`app/models/financial.py`)

```python
class Financial(Base):
    __tablename__ = "financials"

    id               = Column(Integer, primary_key=True)
    company_id       = Column(Integer, ForeignKey("companies.id"), nullable=False)
    year             = Column(Integer, nullable=False)
    roe              = Column(Numeric(10, 4))
    lucro_liquido    = Column(Numeric(20, 2))
    margem_liquida   = Column(Numeric(10, 4))
    receita_liquida  = Column(Numeric(20, 2))
    divida_liquida   = Column(Numeric(20, 2))
    ebitda           = Column(Numeric(20, 2))
    divida_ebitda    = Column(Numeric(10, 4))
    market_cap       = Column(Numeric(20, 2))
    p_l              = Column(Numeric(10, 4))
    cagr_lucro       = Column(Numeric(10, 4))

    company = relationship("Company", back_populates="financials")

    __table_args__ = (UniqueConstraint("company_id", "year"),)
```

### Indexes

Beyond the model definitions, the first Alembic migration should add:

```sql
CREATE INDEX ix_financials_company_year ON financials (company_id, year DESC);
CREATE INDEX ix_companies_asset_type ON companies (asset_type);
```

The `ticker` unique constraint already creates an index. The `company_id + year` unique constraint also serves as an index for the most common query pattern (latest year per company).

### Query Pattern for Analysis

The portfolio analysis path queries the most recent financial record per STOCK:

```python
stmt = (
    select(Company, Financial)
    .join(Financial, Company.id == Financial.company_id)
    .where(Company.ticker == ticker)
    .order_by(Financial.year.desc())
    .limit(1)
)
```

This returns one row: the company metadata + the most recent year's financials. The analysis prompt receives these combined.

### Alembic

- Directory: `migrations/`
- `alembic.ini` `sqlalchemy.url` must use `%(DATABASE_URL)s` and read from environment, not hardcoded
- First migration: auto-generated from model definitions
- All future schema changes go through Alembic — no manual `ALTER TABLE` in production

---

## 5. Pydantic Schemas

### Request Schemas (`app/schemas/portfolio.py`)

```python
class AssetType(str, Enum):
    STOCK   = "STOCK"
    FII     = "FII"
    TESOURO = "TESOURO"

class AssetInput(BaseModel):
    ticker:     str        = Field(..., min_length=1, max_length=10)
    type:       AssetType
    percentage: float      = Field(..., gt=0, le=100)

class PortfolioRequest(BaseModel):
    assets: list[AssetInput] = Field(..., min_length=1)

    @model_validator(mode="after")
    def percentages_must_sum_to_100(self) -> "PortfolioRequest":
        total = sum(a.percentage for a in self.assets)
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Asset percentages must sum to 100, got {total:.2f}")
        return self
```

### Response Schemas (`app/schemas/portfolio.py`)

```python
class BuffettCitation(BaseModel):
    year:      int
    passage:   str
    relevance: str

class FinancialSnapshot(BaseModel):
    roe:           float | None
    margem_liquida: float | None
    cagr_lucro:    float | None
    divida_ebitda: float | None

class StockAssetResponse(BaseModel):
    ticker:                str
    company_name:          str
    sector:                str | None
    type:                  Literal["STOCK"]
    percentage:            float
    score:                 float          # 0.0 to 10.0
    verdict:               str            # "APROVADO" | "ATENÇÃO" | "REPROVADO"
    financials:            FinancialSnapshot
    buffett_verdict:       str
    buffett_citations:     list[BuffettCitation]
    retail_adaptation_note: str

class FIIAssetResponse(BaseModel):
    ticker:     str
    type:       Literal["FII"]
    percentage: float
    verdict:    str = "FII — análise detalhada em breve"

class TesouroAssetResponse(BaseModel):
    ticker:     str
    type:       Literal["TESOURO"]
    percentage: float
    verdict:    str = "Capital seguro"

AssetResponse = Annotated[
    StockAssetResponse | FIIAssetResponse | TesouroAssetResponse,
    Field(discriminator="type")
]

class AlertType(str, Enum):
    TESOURO_LOW      = "TESOURO_LOW"
    TESOURO_ZERO     = "TESOURO_ZERO"
    SINGLE_STOCK_100 = "SINGLE_STOCK_100"
    COMMODITY_HEAVY  = "COMMODITY_HEAVY"
    OVER_CONCENTRATED = "OVER_CONCENTRATED"

class PortfolioAlert(BaseModel):
    type:    AlertType
    message: str

class PortfolioResponse(BaseModel):
    portfolio_grade:   str              # "A", "A-", "B+", "B", ... "F"
    portfolio_summary: str
    portfolio_alerts:  list[PortfolioAlert]
    assets:            list[AssetResponse]
```

### Company Schemas (`app/schemas/company.py`)

```python
class CompanySchema(BaseModel):
    ticker:     str
    name:       str
    sector:     str | None
    segment:    str | None
    asset_type: str

    model_config = ConfigDict(from_attributes=True)

class FinancialHistoryItem(BaseModel):
    year:            int
    roe:             float | None
    lucro_liquido:   float | None
    margem_liquida:  float | None
    receita_liquida: float | None
    divida_liquida:  float | None
    ebitda:          float | None
    divida_ebitda:   float | None
    market_cap:      float | None
    p_l:             float | None
    cagr_lucro:      float | None

    model_config = ConfigDict(from_attributes=True)

class CompanyDetailSchema(CompanySchema):
    financials: list[FinancialHistoryItem]
```

---

## 6. GPT-4o Prompt Design

### Guiding Principles

1. **JSON mode always** — every OpenAI call uses `response_format={"type": "json_object"}`. The system prompt explicitly describes the expected JSON shape. This eliminates parsing fragility.
2. **Legal compliance baked into system prompt** — the prohibition on directive language is in the system prompt, not left to chance.
3. **Retail adaptation is explicit** — the system prompt states Buffett managed billions, not R$ 50k, and instructs GPT-4o to acknowledge this gap.
4. **Citations linked to financial profile** — the passages retrieved from ChromaDB are passed verbatim; GPT-4o's job is to explain *why* each citation is or isn't relevant to this specific company.

### Per-Stock System Prompt

```
You are the Warren Lanchonete analysis engine — a financial analyst with deep knowledge 
of Warren Buffett's investment philosophy adapted for Brazilian retail investors.

IMPORTANT LEGAL RULES — follow these exactly:
- NEVER use: "recomendamos", "sugerimos", "você deve", "é recomendado", "aconselhamos"
- This is a portfolio composition analysis, not investment advice
- Always frame findings as observations about the company, not instructions to the user

TONE:
- Brazilian Portuguese
- Ironic, direct, and slightly humorous without being disrespectful
- Confident but not arrogant

RETAIL CONTEXT:
- Buffett managed billions of dollars — many of his criteria (e.g. moat requiring market 
  dominance at global scale) must be adapted for a retail investor with a diversified 
  portfolio of R$ 10k–500k
- Always include a "retail_adaptation_note" that contextualizes Buffett's standard for 
  this investor's reality

SCORING RUBRIC (score 0.0 to 10.0):
- ROE consistently > 15%: +2 points
- Net margin > 10%: +2 points  
- Debt/EBITDA < 2.0: +2 points
- Profit CAGR > 10% (5 years): +2 points
- Business model durability (sector assessment): +2 points

VERDICT MAPPING:
- score >= 7.0: "APROVADO"
- score >= 4.0: "ATENÇÃO"
- score < 4.0:  "REPROVADO"

OUTPUT FORMAT (JSON):
{
  "score": <float 0.0-10.0>,
  "verdict": <"APROVADO" | "ATENÇÃO" | "REPROVADO">,
  "buffett_verdict": <string, 2-3 sentences in Brazilian Portuguese>,
  "buffett_citations": [
    {
      "year": <int>,
      "passage": <exact passage text>,
      "relevance": <1-2 sentences explaining why this passage applies to this company>
    }
  ],
  "retail_adaptation_note": <string, 1-2 sentences>
}
```

### Per-Stock User Prompt Template

```
Analyze the following Brazilian company from Warren Buffett's perspective:

COMPANY: {company_name} ({ticker})
SECTOR: {sector}
LATEST FINANCIALS ({year}):
- ROE: {roe}%
- Net margin: {margem_liquida}%
- 5-year profit CAGR: {cagr_lucro}%
- Debt/EBITDA: {divida_ebitda}x

BUFFETT PASSAGES (retrieved from his shareholder letters — use these as citations):
{formatted_citations}

Apply the scoring rubric. Explain the score. Cite the most relevant passage.
If no passage is highly relevant, say so in the relevance field.
```

`{formatted_citations}` is rendered as:
```
[1992] "exact passage text here..."
[2000] "another passage text here..."
[2007] "third passage text here..."
```

### Portfolio Summary System Prompt

```
You are the Warren Lanchonete portfolio grader.

LEGAL RULES: Same as per-stock prompt — no directive language.

TONE: Same as per-stock prompt.

GRADING SCALE:
A  — Buffett would be proud. Mostly quality businesses, good diversification, protected downside.
A- — Very good. Minor concentration or one weaker holding.
B+ — Good, but something stands out (high concentration, one bad pick, low safety net).
B  — Decent but multiple areas to watch.
B- — More concerns than positives.
C  — Significant issues: over-concentration, poor quality businesses, no safety net.
D  — Mostly speculative or high-debt companies.
F  — Buffett would not recognize this as investing.

OUTPUT FORMAT (JSON):
{
  "portfolio_grade": <"A"|"A-"|"B+"|"B"|"B-"|"C+"|"C"|"C-"|"D"|"F">,
  "portfolio_summary": <string, 3-5 sentences in Brazilian Portuguese>
}
```

### Portfolio Summary User Prompt Template

```
Grade this portfolio:

ASSETS:
{for each stock: ticker, score, verdict, sector, percentage}
{for each FII: ticker, percentage — "deep analysis pending"}
{for each TESOURO: ticker, percentage — "safe capital"}

ALERTS DETECTED: {list of alert types and messages, or "none"}

Consider: diversification, quality of stock picks, presence of safe capital buffer,
concentration risk, sector overlap.

Apply the grading scale. Write the summary in Brazilian Portuguese.
```

### Handling Missing Citations

When `RAGService` returns an empty list (ChromaDB has no results), the prompt is still sent to GPT-4o but the citations section reads:

```
BUFFETT PASSAGES: None retrieved. Assess the company based on financials alone.
```

GPT-4o will return `buffett_citations: []` in the JSON output. The response schema allows an empty list.

---

## 7. Tone of Voice Trigger System

### Design Decision

Triggers are detected deterministically in `PortfolioService` — not by GPT-4o — because:
1. Pre-written phrases must appear verbatim (brand consistency)
2. GPT-4o may paraphrase or choose a different phrase
3. Detection logic is simple and testable

### Trigger Detection Logic

All detection runs after the per-stock results are assembled but before the portfolio summary prompt is sent.

```python
def detect_alerts(assets: list[AssetInput]) -> list[PortfolioAlert]:
    alerts = []
    tesouro_pct = sum(a.percentage for a in assets if a.type == "TESOURO")
    stock_percentages = {a.ticker: a.percentage for a in assets if a.type == "STOCK"}
    
    # TESOURO_ZERO takes precedence over TESOURO_LOW
    if tesouro_pct == 0:
        alerts.append(PortfolioAlert(
            type=AlertType.TESOURO_ZERO,
            message="Sem paraquedas? Corajoso."
        ))
    elif tesouro_pct < 5:
        # Alternate between two phrases based on... just use the first for now
        alerts.append(PortfolioAlert(
            type=AlertType.TESOURO_LOW,
            message="É muita coragem ter tão pouca renda fixa"
        ))
    
    # 100% single stock
    for ticker, pct in stock_percentages.items():
        if pct >= 99.9:
            alerts.append(PortfolioAlert(
                type=AlertType.SINGLE_STOCK_100,
                message="Colocou todos os ovos na mesma cesta, hein..."
            ))
    
    # High commodity concentration (PETR4, VALE3, CMIN3, etc.)
    COMMODITY_TICKERS = {"PETR4", "PETR3", "VALE3", "CMIN3", "CSNA3", "GGBR4"}
    commodity_pct = sum(
        pct for t, pct in stock_percentages.items()
        if t in COMMODITY_TICKERS
    )
    if commodity_pct > 40:
        alerts.append(PortfolioAlert(
            type=AlertType.COMMODITY_HEAVY,
            message="Torce muito pro petróleo, né?"
        ))
    
    # Over-concentration: top-2 assets > 80% of portfolio
    all_pcts = sorted([a.percentage for a in assets], reverse=True)
    if len(all_pcts) >= 2 and (all_pcts[0] + all_pcts[1]) > 80:
        alerts.append(PortfolioAlert(
            type=AlertType.OVER_CONCENTRATED,
            message="Diversificação? Nunca ouvi falar."
        ))
    
    return alerts
```

The alerts list is:
1. Included verbatim in the `PortfolioResponse.portfolio_alerts` field
2. Passed to the portfolio summary prompt so GPT-4o can reference them in the narrative

### Phrase Rotation (Future)

The design doc lists two alternative phrases for `TESOURO_LOW`. In v1, always use the first. In v2, implement a deterministic rotation based on `hash(portfolio_tickers) % 2` so the same portfolio always gets the same phrase (avoids confusion on resubmit), but different portfolios get variety.

---

## 8. PDF Export

### Trigger

Optional query parameter on the analyze endpoint: `POST /api/portfolio/analyze?format=pdf`

The router checks `format: str | None = Query(default=None)`. If `format == "pdf"`, after receiving the `PortfolioResponse`, it calls `PDFService.generate(response)` and returns:

```python
return StreamingResponse(
    io.BytesIO(pdf_bytes),
    media_type="application/pdf",
    headers={"Content-Disposition": "attachment; filename=\"warren_report.pdf\""}
)
```

### Template Design (`templates/report.html`)

The Jinja2 template must be self-contained (all CSS inline or embedded in `<style>`) because WeasyPrint does not execute JavaScript and has limited support for external stylesheets at runtime.

Template sections:
1. **Header** — Warren Lanchonete logo (SVG inline), analysis date, disclaimer text
2. **Portfolio Overview** — grade badge (large, colored), portfolio summary text, alerts list
3. **Asset Cards** — one card per asset
   - STOCK card: company name, ticker, sector, score bar (CSS), verdict badge, financials table, Buffett verdict, citations block, retail note
   - FII card: ticker, percentage, "análise detalhada em breve" pill
   - TESOURO card: ticker, percentage, "Capital seguro" badge
4. **Footer** — legal disclaimer: "Esta análise é meramente informativa e não constitui recomendação de investimento. Consulte um assessor de investimentos certificado."

### Legal Disclaimer

The PDF must contain the disclaimer on every page footer. Implement via CSS `@page` rule with `content` property for the footer.

### CSS Color Coding

Verdict colors (for both web response metadata and PDF):
- "APROVADO" → green (`#22c55e`)
- "ATENÇÃO" → amber (`#f59e0b`)
- "REPROVADO" → red (`#ef4444`)

Grade colors: A/A- → green; B+/B/B- → blue; C+/C/C- → amber; D/F → red

---

## 9. Error Handling Map

### Typed Exceptions (`app/exceptions.py` — create this file)

```python
class WarrenBaseError(Exception):
    pass

class TickerNotFoundError(WarrenBaseError):
    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"Ticker {ticker} not found in database")

class OpenAIUnavailableError(WarrenBaseError):
    pass

class RAGEmptyResultError(WarrenBaseError):
    """Not raised — empty results are handled gracefully."""
    pass

class PDFGenerationError(WarrenBaseError):
    pass
```

### Exception Handlers (registered in `app/main.py`)

```python
@app.exception_handler(TickerNotFoundError)
async def ticker_not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(OpenAIUnavailableError)
async def openai_unavailable_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": "Analysis service temporarily unavailable. Try again in a moment."}
    )

@app.exception_handler(PDFGenerationError)
async def pdf_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": "PDF generation failed"})
```

### Error Handling Table

| Scenario | Where Detected | Exception Raised | HTTP Status | Response Body |
|---|---|---|---|---|
| Ticker not in `companies` table | `PortfolioService` | `TickerNotFoundError` | 404 | `{"detail": "Ticker XXXX not found in database"}` |
| Percentages don't sum to 100 | Pydantic validator | `ValidationError` | 422 | FastAPI default validation error body |
| Unknown asset type | Pydantic validator | `ValidationError` | 422 | FastAPI default validation error body |
| OpenAI `APIConnectionError` | `AnalysisService` | `OpenAIUnavailableError` | 503 | `{"detail": "Analysis service temporarily unavailable..."}` |
| OpenAI `APITimeoutError` | `AnalysisService` | `OpenAIUnavailableError` | 503 | same |
| OpenAI returns invalid JSON | `AnalysisService` | `OpenAIUnavailableError` | 503 | same |
| ChromaDB empty results | `RAGService` | not raised — returns `[]` | N/A | Citations empty in response |
| ChromaDB client error | `RAGService` | logged + returns `[]` | N/A | Citations empty, analysis continues |
| PDF generation failure | `PDFService` | `PDFGenerationError` | 500 | `{"detail": "PDF generation failed"}` |
| Single stock timeout | `PortfolioService.gather` | caught internally | N/A | That asset gets degraded verdict, others proceed |
| DB connection failure | SQLAlchemy | propagates → 500 | 500 | Generic error with correlation ID |

### Partial Degradation for Per-Stock Analysis

If one stock's analysis times out or OpenAI returns an error for that specific call, `PortfolioService` catches it and substitutes a degraded response:

```python
StockAssetResponse(
    ...same company/financials fields...,
    score=0.0,
    verdict="ATENÇÃO",
    buffett_verdict="Análise indisponível no momento. Tente novamente.",
    buffett_citations=[],
    retail_adaptation_note=""
)
```

The portfolio summary prompt receives all results including the degraded one and is instructed to ignore missing analysis when computing the grade.

---

## 10. Config

### `Settings` Class (`app/config.py`)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Required
    OPENAI_API_KEY:    str
    DATABASE_URL:      str

    # Optional with defaults
    CHROMA_PERSIST_DIR:     str   = "./rag_data"
    OPENAI_MODEL:           str   = "gpt-4o"
    EMBEDDING_MODEL:        str   = "text-embedding-3-small"
    RAG_TOP_K:              int   = 3
    OPENAI_TIMEOUT_SECONDS: int   = 30
    ENVIRONMENT:            str   = "development"
    CORS_ORIGINS:           str   = "http://localhost:3000"  # comma-separated
    LOG_LEVEL:              str   = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Module-level singleton — import this everywhere
settings = Settings()
```

### Usage Pattern

Services and modules import: `from app.config import settings`

Never use `os.environ.get()` directly in service or router code. All config access goes through the `settings` object.

### Secret Management

- Development: `.env` file (git-ignored)
- Production (Hostinger VPS): environment variables set in the systemd service unit or via `export` in the shell profile — NOT in any file committed to git
- Future: HashiCorp Vault agent sidecar (out of scope for v1)

---

## 11. Observability

### Structured Logging

Use `structlog` (add to dependencies). Configure in `app/main.py` to output JSON in production and colored console in development.

Every log entry must include:
- `trace_id` — generated per-request by middleware (UUID4, stored in `contextvars.ContextVar`)
- `service` — `"warren-backend"`
- `environment` — from `settings.ENVIRONMENT`

Key log events:
- `portfolio.analysis.started` — tickers and types received
- `portfolio.stock.analysis.started` / `.completed` / `.failed` — per ticker
- `portfolio.summary.started` / `.completed`
- `rag.retrieve.started` / `.completed` — query string and number of results
- `openai.call.started` / `.completed` / `.failed` — model, token counts (from response)

### Distributed Tracing

Add `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy` to dependencies.

Configure in `app/main.py` lifespan. Export to stdout (OTLP/stdout) for v1. In production, point to a local Jaeger or Grafana Tempo instance via `OTEL_EXPORTER_OTLP_ENDPOINT`.

### Prometheus Metrics

Add `prometheus-fastapi-instrumentator` to dependencies. Mount at `/metrics`. This auto-instructs all routes with:
- `http_requests_total` (counter, labeled by method + path + status)
- `http_request_duration_seconds` (histogram)

Add custom application metrics in services:
- `warren_openai_calls_total` (counter, labeled by call_type: "per_stock" | "summary")
- `warren_openai_duration_seconds` (histogram, labeled by call_type)
- `warren_rag_results_total` (histogram of results count per query)

### Health Endpoints

```
GET /health   → {"status": "ok"}                        # always 200 if process is running
GET /ready    → {"status": "ok"} or 503 with detail     # checks DB + ChromaDB
GET /metrics  → Prometheus text format
```

The `/ready` handler:
1. Attempts `SELECT 1` on the DB connection pool
2. Calls `chroma_client.get_collection("buffett_letters")` to verify collection exists
3. Returns 200 only if both pass

### SLO Targets

| SLO | Target | Alerting Threshold |
|---|---|---|
| `/api/portfolio/analyze` p99 latency | < 15s | Alert if > 20s (OpenAI-dependent) |
| `/api/companies` p99 latency | < 200ms | Alert if > 500ms |
| Error rate (5xx) | < 1% | Alert if > 2% over 5 min |
| `/ready` availability | > 99.9% | Alert if fails 3 consecutive checks |

Note: the analyze endpoint latency target is set at 15s (not the typical 200ms) because it makes multiple sequential GPT-4o calls. This should be communicated to the frontend for UX purposes (show loading state).

---

## 12. Security

### Input Validation

- All inputs validated by Pydantic at the router boundary before any service code runs
- Ticker strings: `max_length=10`, no special characters (consider adding `pattern=r"^[A-Z0-9]+$"` regex validator)
- Percentage: validated as > 0 and <= 100; sum validated at portfolio level
- No user-supplied strings are ever interpolated into SQL (SQLAlchemy ORM prevents injection by default)
- No user-supplied strings are inserted into ChromaDB queries without sanitization

### Prompt Injection Protection

User-supplied ticker strings must never be passed raw into the GPT-4o prompt. The prompt is constructed exclusively from DB-sourced company data (name, sector, financials) and ChromaDB-retrieved passages. The ticker is only used as a DB lookup key.

### API Key Security

- `OPENAI_API_KEY` read from environment only — never logged, never included in error responses
- The `structlog` configuration must include a processor to redact any field named `api_key`, `secret`, or `password`

### CORS

- `CORS_ORIGINS` in Settings — comma-separated list of allowed origins
- In production: only the deployed Next.js frontend URL
- `allow_credentials=False` (no cookies used)
- `allow_methods=["GET", "POST"]` only

### Rate Limiting (Future)

Not implemented in v1. On the Hostinger VPS, Nginx can be configured with `limit_req_zone` to rate-limit the analyze endpoint (it calls OpenAI — cost protection). Recommended: 10 requests/minute per IP.

### Authentication (Future / Out of Scope v1)

No authentication in v1 — the API is publicly accessible. When user accounts are added (future scope), implement JWT validation at the FastAPI middleware level using `python-jose` or `authlib`. RBAC is not needed for v1 since there is only one user-facing role.

---

## 13. Suggestions and Gaps

The following are gaps or improvement opportunities identified during architecture design relative to the design doc.

### S1: Missing `pydantic-settings` in `pyproject.toml`

`pydantic-settings` is required for the `Settings` class but is not listed in the current `pyproject.toml`. Add it. Also missing: `asyncpg` (async PostgreSQL driver), `aiosqlite` (for test fixtures), `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-mock`, `structlog`, `prometheus-fastapi-instrumentator`.

### S2: Async SQLAlchemy vs Sync

The current `pyproject.toml` lists `psycopg2-binary` (synchronous driver). For a fully async FastAPI service, `asyncpg` (async driver) should be added alongside SQLAlchemy's async extension. Alternatively, use `psycopg[async]` (psycopg3). Using the sync driver with an async framework works but blocks the event loop on every DB query, negating the concurrency benefits of `asyncio.gather`.

### S3: ChromaDB Thread Safety

ChromaDB's `PersistentClient` is not async-native. With `asyncio.gather` firing multiple `retrieve()` calls concurrently, all hitting the same ChromaDB instance, there may be contention. ChromaDB uses SQLite under the hood for metadata — concurrent reads on SQLite are safe (WAL mode), but verify this with a load test. If contention is observed, serialize ChromaDB access with an `asyncio.Semaphore(1)` around retrievals.

### S4: Tone of Voice — COMMODITY_TICKERS Hardcoded

The commodity ticker list (`PETR4`, `VALE3`, etc.) is hardcoded in the trigger detection logic. A cleaner approach: the `companies` table has a `sector` column. Use sector-based detection: `sector IN ('Petróleo e Gás', 'Mineração', 'Siderurgia')` instead of ticker matching. This way, new commodity stocks added to the DB are automatically covered.

### S5: FII Asset — No DB Lookup

In the current design, FII assets are returned with a fixed verdict string without any DB lookup. This means unknown FII tickers pass through silently. Recommendation: still validate that the FII ticker exists in the `companies` table (with `asset_type = 'FII'`) and return `company_name` in the FII response object. The `warren-ingestion` repo should seed FII companies as well. Return `404` for unknown FII tickers the same as for STOCKs.

### S6: TESOURO Breakdown (Future Scope, but Schema Impact)

The design doc marks Tesouro type breakdown as out of scope for v1. However, the ticker `"TESOURO"` is a single string in the current contract. When v2 adds breakdown (SELIC vs IPCA+ vs Prefixado), the ticker field will need to change (e.g., `"TESOURO_SELIC"`, `"TESOURO_IPCA_PLUS"`). Consider whether the v1 contract should allow a `tesouro_type` field (nullable, ignored for now) to avoid a breaking API change in v2.

### S7: RAG Topic Tagging Not Implemented

The design doc specifies `"topic": "moat, pricing_power, returns_on_capital"` in the chunk metadata, but the ingestion script design leaves this empty for v1. Topic tagging would significantly improve retrieval precision — an industrial company with high ROE should retrieve passages about "returns on capital" and "durable competitive advantage", not passages about insurance or banking. Recommend adding rule-based topic tagging in the ingestion script based on keyword detection per chunk before v1 goes to production.

### S8: No Caching Layer

Every `POST /analyze` call makes N OpenAI calls (N = number of stocks). For a user who submits the same portfolio twice, the results will be identical. Consider an in-memory cache (Python `functools.lru_cache` or `cachetools.TTLCache`) keyed by `(ticker, year)` for per-stock analysis results, with a TTL of 24 hours. This would eliminate redundant OpenAI calls for common tickers and reduce cost significantly.

### S9: No Request Deduplication

If a user clicks "Analyze" twice rapidly, two identical requests may be in-flight simultaneously. Given OpenAI costs, add a simple request deduplication layer: hash the sorted portfolio tickers+percentages, store in-memory with a 30s TTL, return cached response if same hash arrives within TTL.

### S10: PDF Template Needs Brazilian Portuguese Legal Disclaimer

The legal disclaimer in the PDF footer must explicitly state "Esta análise é informativa e não constitui recomendação de investimento" (and equivalent CVM compliance language). The exact wording should be reviewed by a legal professional familiar with CVM Resolution 35/2021 before production launch.

### S11: Ingestion Script Has No Duplicate-Check Efficiency

The current idempotency design checks each chunk individually before inserting. With 1000+ chunks, this means 1000+ DB lookups. A more efficient approach: before ingesting a PDF, check if any chunk with `source_file = "1992_letter.pdf"` exists in the collection. If yes, skip the entire file. This reduces startup time for re-runs from minutes to seconds.
