# Warren Lanchonete — Design Document

**Date:** 2026-04-27
**Status:** Approved

---

## Overview

Web app that analyzes Brazilian investor portfolios through the lens of Warren Buffett's investment philosophy. The user inputs their assets and allocation percentages (no monetary values). The app generates a report with per-asset scores and an overall portfolio grade, backed by RAG retrieval from Buffett's shareholder letters and real financial data from Brazilian companies.

**Target user:** Retail Brazilian investors who want a second opinion on their portfolio composition.

---

## Goals

- Analyze portfolio composition using Buffett's criteria adapted for retail investors
- Generate per-asset verdicts + overall portfolio grade
- Use Buffett's letters as RAG knowledge base (with citations)
- Adapt Buffett's advice to retail context (he managed billions — not everything applies)
- Never use directive language ("recomendamos", "você deve") — legal compliance with CVM
- Use humor and irony for a memorable Brazilian personality

---

## Asset Types

Three buckets are supported:

| Type | Treatment |
|------|-----------|
| `STOCK` | Full Buffett analysis — score, verdict, citations |
| `FII` | Recognized in portfolio, percentage shown, deep analysis is future scope |
| `TESOURO` | Grouped as "capital seguro" — warns (with humor) if below 5% |

---

## Architecture

### Three Separate Repos / Agents

```
warrenlanchonete/
├── warren-backend/      ← Claude agent
├── warren-frontend/     ← GPT-5.5 Codex Pro agent
└── warren-ingestion/    ← GPT-5.5 Codex Pro agent
```

### High-Level Diagram

```
FRONTEND (Next.js + Tailwind)
  └── REST API (OpenAPI contract)
        └── BACKEND (FastAPI + Python)
              ├── PostgreSQL  (financial data — own database)
              ├── ChromaDB    (Buffett letters — RAG)
              └── OpenAI      (GPT-4o — analysis + report)

INGESTION PIPELINE (Scrapy — runs separately, not at runtime)
  └── Status Invest / Fundamentus / B3
        └── PostgreSQL (seed + quarterly updates)
```

### Agent Assignments

| Repo | Agent | Responsibility |
|------|-------|----------------|
| `warren-backend` | Claude | FastAPI, RAG, ChromaDB, GPT-4o prompt engineering |
| `warren-frontend` | GPT-5.5 Codex Pro | Next.js, Tailwind, cards, PDF export |
| `warren-ingestion` | GPT-5.5 Codex Pro | Scrapy spiders, data cleaning, PostgreSQL seed |

---

## Data Flow (Runtime)

```
1. User submits portfolio
   [WEGE3: 35%, MXRF11: 15%, TESOURO: 10%, PETR4: 40%]

2. FastAPI validates input
   → check percentages sum to 100%
   → identify asset types (STOCK, FII, TESOURO)

3. For each STOCK:
   → query PostgreSQL (own database, no external call)
   → retrieve top-3 Buffett passages from ChromaDB
     (query built from: sector + ROE profile + debt level)
   → each passage tagged with year (temporal awareness)

4. GPT-4o analysis
   → one prompt per STOCK asset
   → system prompt enforces: retail adaptation + tone of voice
   → output: score (0-10), verdict, Buffett citation, retail note

5. GPT-4o portfolio summary
   → all per-asset results as input
   → output: overall grade (A–F), portfolio insights, risk flags

6. Response assembled as JSON
   → frontend renders cards
   → user can export as PDF (WeasyPrint on backend)
```

---

## Data Flow (Ingestion — not at runtime)

```
Scrapy spiders
  → Status Invest: ROE, P/L, margem líquida, dívida/EBITDA, CAGR
  → Fundamentus: cross-validation
  → clean + normalize
  → insert into PostgreSQL

Runs: once to seed, then quarterly during earnings season
```

---

## Database Schema (PostgreSQL)

Shared contract between `warren-ingestion` and `warren-backend`.

```sql
-- One row per company
CREATE TABLE companies (
  id          SERIAL PRIMARY KEY,
  ticker      VARCHAR(10) UNIQUE NOT NULL,
  name        VARCHAR(200) NOT NULL,
  sector      VARCHAR(100),
  segment     VARCHAR(100),
  asset_type  VARCHAR(10) NOT NULL  -- 'STOCK' or 'FII'
);

-- Historical fundamentals — immutable once inserted
CREATE TABLE financials (
  id               SERIAL PRIMARY KEY,
  company_id       INTEGER REFERENCES companies(id),
  year             INTEGER NOT NULL,
  roe              DECIMAL(10,4),    -- Return on Equity %
  lucro_liquido    DECIMAL(20,2),    -- Net profit R$
  margem_liquida   DECIMAL(10,4),    -- Net margin %
  receita_liquida  DECIMAL(20,2),    -- Net revenue R$
  divida_liquida   DECIMAL(20,2),    -- Net debt R$
  ebitda           DECIMAL(20,2),
  divida_ebitda    DECIMAL(10,4),    -- Debt/EBITDA
  market_cap       DECIMAL(20,2),
  p_l              DECIMAL(10,4),    -- P/E ratio
  cagr_lucro       DECIMAL(10,4),    -- 5-year profit CAGR
  UNIQUE(company_id, year)
);
```

---

## API Contract (FastAPI → Next.js)

### POST /api/portfolio/analyze

**Request:**
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

**Response:**
```json
{
  "portfolio_grade": "B+",
  "portfolio_summary": "...",
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
      "buffett_verdict": "...",
      "buffett_citations": [
        {
          "year": 1992,
          "passage": "...",
          "relevance": "..."
        }
      ],
      "retail_adaptation_note": "..."
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

### GET /api/companies
Returns list of all available tickers with name, sector and type.

### GET /api/companies/{ticker}
Returns full financial history for a ticker.

---

## RAG Design

**Vector store:** ChromaDB (persisted on disk in `warren-backend/rag_data/`)

**Collection:** `buffett_letters`

**Chunk metadata:**
```json
{
  "year": 1992,
  "letter_type": "shareholder_letter",
  "topic": "moat, pricing_power, returns_on_capital"
}
```

**Retrieval strategy:** semantic query built from company profile:
```
"Brazilian industrial company, high ROE (28%), low debt, durable competitive advantage"
```
→ returns top-3 passages, filtered to avoid outdated advice flagged by year.

**Buffett letters ingestion pipeline:**
```
PDFs → PyMuPDF (text extraction)
     → chunk by paragraph (~300 tokens)
     → tag with year + topic
     → OpenAI embeddings (text-embedding-3-small)
     → store in ChromaDB
```

---

## Tone of Voice

**Legal rule:** Never use "recomendamos", "sugerimos", "você deve".
This app analyzes composition — it does not give financial advice.

**Style:** Ironic, humorous, direct Brazilian Portuguese.

**Trigger phrases (pre-written, GPT-4o chooses contextually):**

| Trigger | Phrase |
|---------|--------|
| Tesouro < 5% | "É muita coragem ter tão pouca renda fixa" |
| Tesouro < 5% alt | "É sempre bom ficar com a bundinha na parede e ter um capital alocado em segurança" |
| Tesouro = 0% | "Sem paraquedas? Corajoso." |
| 100% em uma ação | "Colocou todos os ovos na mesma cesta, hein..." |
| Alta concentração em commodities | "Torce muito pro petróleo, né?" |
| Portfolio muito concentrado | "Diversificação? Nunca ouvi falar." |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI (Python) |
| ORM | SQLAlchemy + Alembic |
| Database | PostgreSQL |
| RAG | LangChain + ChromaDB |
| LLM | OpenAI GPT-4o |
| Embeddings | OpenAI text-embedding-3-small |
| PDF ingestion | PyMuPDF |
| PDF export | WeasyPrint |
| Templates | Jinja2 |
| Scraping | Scrapy |
| Frontend | Next.js + Tailwind CSS |
| UI style | Friendly, card-based (Nubank-inspired) |
| Hosting | Hostinger VPS (Nginx + Uvicorn) |

---

## Out of Scope (v1)

- FII deep analysis (sector, vacância, dividend yield)
- International stocks (ADRs, BDRs)
- Tesouro type breakdown (SELIC vs IPCA+ vs Prefixado)
- User accounts / saved portfolios
- Real-time price data
- Push notifications

---

## Future Scope

- FII analysis module
- Company screener (use own database)
- Sector comparison charts
- Portfolio evolution tracking over time
- Swap Scrapy to a paid API (Brapi, HG Finance) for reliability
