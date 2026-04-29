# End-to-End Backend Test Report

Date: 2026-04-28

## Test Attempt 1: Start Backend With `.env`

Command:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Result: failed during FastAPI startup before any HTTP endpoint could be tested.

Observed log:

```text
AttributeError: 'PrintLogger' object has no attribute 'name'
```

The crash happens in `app/main.py` during lifespan startup:

```python
logger.info("warren_backend.startup", environment=env)
```

The underlying failure is in structlog:

```text
structlog.stdlib.add_logger_name
event_dict["logger"] = logger.name
AttributeError: 'PrintLogger' object has no attribute 'name'
```

## Explanation

`app/logging_config.py` configures structlog with stdlib processors:

```python
structlog.stdlib.add_logger_name
structlog.stdlib.add_log_level
```

but it also uses:

```python
logger_factory=structlog.PrintLoggerFactory()
```

`structlog.stdlib.add_logger_name` expects a stdlib logger that has `.name`.
`PrintLoggerFactory()` creates a `PrintLogger`, which does not have `.name`.
So the first log call after `configure_logging()` crashes the app startup.

## Proposed Fix

Change the logger factory in `app/logging_config.py` from `PrintLoggerFactory`
to the stdlib logger factory:

```python
logger_factory=structlog.stdlib.LoggerFactory(),
```

Keep the current processors and renderers. This matches the existing use of
`structlog.stdlib.add_logger_name` and `structlog.stdlib.add_log_level`.

## Validation After Fix

1. Start backend:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

2. Test basic endpoints:

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/ready
curl http://127.0.0.1:8001/api/companies
curl http://127.0.0.1:8001/api/companies/WEGE3
```

3. Test portfolio analysis endpoint:

```bash
curl -X POST http://127.0.0.1:8001/api/portfolio/analyze \
  -H 'Content-Type: application/json' \
  -d '{"assets":[{"ticker":"WEGE3","type":"STOCK","percentage":60},{"ticker":"TESOURO","type":"TESOURO","percentage":40}]}'
```

## Status

Applied with permission. Startup now passes this point.

## Test Attempt 2: Basic HTTP Endpoints After Logging Fix

Command:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Result: backend starts successfully, but startup is degraded:

```text
warren_backend.rag_init_failed
error='The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable'
rag_service_initialized=False
```

Endpoint checks:

```bash
curl http://127.0.0.1:8001/health
```

Result:

```http
HTTP/1.1 200 OK
{"status":"ok"}
```

```bash
curl http://127.0.0.1:8001/ready
```

Result:

```http
HTTP/1.1 503 Service Unavailable
{"status":"degraded","detail":"DB unavailable: [Errno 111] Connection refused; ChromaDB not initialized"}
```

```bash
curl http://127.0.0.1:8001/api/companies
```

Result:

```http
HTTP/1.1 500 Internal Server Error
Internal Server Error
```

Server log for `/api/companies`:

```text
ConnectionRefusedError: [Errno 111] Connection refused
```

## Explanation

There are two independent failures now:

1. Database connectivity is failing.

   The `.env` file currently points to:

   ```text
   DATABASE_URL=postgresql://user:password@localhost:5432/warren
   ```

   The Docker Compose dev database is configured as:

   ```text
   POSTGRES_USER=warren
   POSTGRES_PASSWORD=password
   POSTGRES_DB=warren
   ```

   Expected backend URL for the local dev database:

   ```text
   DATABASE_URL=postgresql://warren:password@localhost:5432/warren
   ```

   Because the backend cannot connect, `/ready` reports DB unavailable and
   `/api/companies` returns 500.

2. RAG/OpenAI initialization is failing even though `.env` contains
   `OPENAI_API_KEY`.

   The app loads `.env` into `Settings`, but `LangChain OpenAIEmbeddings`
   expects the key through either:

   - an explicit `api_key=...` constructor argument, or
   - `OPENAI_API_KEY` present in `os.environ`

   Current code in `app/services/rag_service.py` creates embeddings without
   passing the key:

   ```python
   OpenAIEmbeddings(model=settings.EMBEDDING_MODEL)
   ```

   Since Pydantic settings does not automatically export values back into
   `os.environ`, LangChain cannot see the API key.

## Proposed Fixes

1. Update local `.env` database URL to the Docker Compose dev database:

   ```text
   DATABASE_URL=postgresql://warren:password@localhost:5432/warren
   ```

2. Update `app/services/rag_service.py` to pass the configured API key directly:

   ```python
   OpenAIEmbeddings(
       model=settings.EMBEDDING_MODEL,
       api_key=settings.OPENAI_API_KEY,
   )
   ```

3. Check `app/services/analysis_service.py` for the same pattern. If it depends
   on environment lookup instead of explicit settings, pass the configured API
   key there too.

## Validation After Fixes

1. Restart backend.
2. Verify:

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/ready
curl http://127.0.0.1:8001/api/companies
curl http://127.0.0.1:8001/api/companies/WEGE3
```

3. Then test:

```bash
curl -X POST http://127.0.0.1:8001/api/portfolio/analyze \
  -H 'Content-Type: application/json' \
  -d '{"assets":[{"ticker":"WEGE3","type":"STOCK","percentage":60},{"ticker":"TESOURO","type":"TESOURO","percentage":40}]}'
```

## Status

Waiting for permission to apply the proposed `.env` and RAG/OpenAI key wiring fixes.

Applied with permission:

- `.env` now points to `postgresql://warren:password@localhost:5432/warren`
- `RAGService` now passes `settings.OPENAI_API_KEY` into `OpenAIEmbeddings`

## Test Attempt 3: Restart After `.env` and RAG Fixes

Command:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Result: backend starts successfully and RAG initializes:

```text
warren_backend.ready rag_service_initialized=True
```

Endpoint checks:

```bash
curl http://127.0.0.1:8001/health
```

Result:

```http
HTTP/1.1 200 OK
{"status":"ok"}
```

```bash
curl http://127.0.0.1:8001/ready
```

Result:

```http
HTTP/1.1 503 Service Unavailable
{"status":"degraded","detail":"DB unavailable: [Errno 111] Connection refused; ChromaDB collection 'buffett_letters' is empty — run: uv run python -m app.rag.ingest"}
```

```bash
curl http://127.0.0.1:8001/api/companies
curl http://127.0.0.1:8001/api/companies/WEGE3
```

Result:

```http
HTTP/1.1 500 Internal Server Error
```

Server log:

```text
ConnectionRefusedError: [Errno 111] Connection refused
```

Direct socket check:

```bash
uv run python -c 'import socket; s=socket.socket(); s.settimeout(3); s.connect(("127.0.0.1", 5432)); print("connected")'
```

Result:

```text
ConnectionRefusedError: [Errno 111] Connection refused
```

## Explanation

The backend is now configured with the correct dev database URL, but no process
is accepting TCP connections on `127.0.0.1:5432` from this environment.

This is not currently a backend code problem. It means the Postgres container is
not running, not publishing port 5432, or is unreachable from the process running
the backend.

I cannot verify Docker directly from this agent because the current user cannot
read the Docker socket:

```text
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

There is also a separate readiness warning that ChromaDB is empty. That will
block `/ready` from returning 200 even after Postgres is reachable, but it should
not block `/api/companies`.

## Required External Action

Run from the repo root:

```bash
sudo docker compose ps db
sudo docker compose up -d db
sudo docker compose logs --tail=100 db
```

Then verify the port is reachable:

```bash
nc -vz localhost 5432
```

If `nc` is not installed:

```bash
python -c 'import socket; s=socket.socket(); s.settimeout(3); s.connect(("127.0.0.1", 5432)); print("connected")'
```

After Postgres is reachable, rerun:

```bash
cd warren-backend
uv run alembic upgrade head
uv run python -m app.db.seed
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

## Status

Blocked on local Postgres availability. No further backend code fix is proposed
for this failure until port `5432` is reachable.

Resolved after Docker Postgres was restarted. Direct socket check now passes:

```text
connected
```

Migrations and seed were rerun:

```bash
uv run alembic upgrade head
uv run python -m app.db.seed
```

Seed result:

```text
companies_created=0 companies_updated=4 financials_created=0 financials_updated=3
```

## Test Attempt 4: DB-Backed Endpoints After Postgres Recovery

Command:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Startup result:

```text
warren_backend.ready rag_service_initialized=True
```

Endpoint checks:

```bash
curl http://127.0.0.1:8001/health
```

Result:

```http
HTTP/1.1 200 OK
{"status":"ok"}
```

```bash
curl http://127.0.0.1:8001/api/companies
```

Result:

```http
HTTP/1.1 200 OK
```

Returned companies:

```text
MXRF11
PETR4
TESOURO
WEGE3
```

```bash
curl http://127.0.0.1:8001/api/companies/WEGE3
```

Result:

```http
HTTP/1.1 200 OK
```

Returned expected 2024 WEGE3 financial data:

```text
roe=28.5
margem_liquida=15.2
divida_ebitda=0.4
cagr_lucro=18.3
```

Readiness is still degraded:

```http
HTTP/1.1 503 Service Unavailable
{"status":"degraded","detail":"ChromaDB collection 'buffett_letters' is empty — run: uv run python -m app.rag.ingest"}
```

This is expected until RAG data is ingested.

## Test Attempt 5: Portfolio Analysis

Command:

```bash
curl -X POST http://127.0.0.1:8001/api/portfolio/analyze \
  -H 'Content-Type: application/json' \
  -d '{"assets":[{"ticker":"WEGE3","type":"STOCK","percentage":60},{"ticker":"TESOURO","type":"TESOURO","percentage":40}]}'
```

Result:

```http
HTTP/1.1 503 Service Unavailable
{"detail":"Analysis service temporarily unavailable. Try again in a moment."}
```

Server logs:

```text
POST https://api.openai.com/v1/embeddings "HTTP/1.1 429 Too Many Requests"
rag.retrieve.failed error="Error code: 429 ... insufficient_quota"

POST https://api.openai.com/v1/chat/completions "HTTP/1.1 429 Too Many Requests"
openai.call.failed call_type=per_stock error="Error code: 429 ... insufficient_quota"

POST https://api.openai.com/v1/chat/completions "HTTP/1.1 429 Too Many Requests"
openai.call.failed call_type=summary error="Error code: 429 ... insufficient_quota"
```

## Explanation

The DB-backed API surface is now working.

The portfolio analysis endpoint fails because the configured OpenAI account/key
has insufficient quota. This is not a database issue.

There is also one backend/data-layer inefficiency:

- `/ready` already knows the `buffett_letters` ChromaDB collection is empty.
- `RAGService.retrieve()` still calls `similarity_search()`, which triggers an
  OpenAI embeddings request.
- Because the collection is empty, this request cannot return useful citations
  and wastes quota.

## Proposed Fix

Add an empty-collection guard in `RAGService.retrieve()` before similarity search:

```python
collection = self._chroma_client.get_or_create_collection("buffett_letters")
if collection.count() == 0:
    logger.warning("rag.retrieve.empty_collection", ticker=ticker)
    return []
```

This will avoid unnecessary embedding calls when no RAG data has been ingested.

This will not fix the final portfolio summary call. To complete a real E2E
portfolio analysis, one of these is still required:

1. Use an OpenAI key/account with available quota.
2. Add a local/mock analysis mode for development E2E tests.

## Status

Waiting for permission to apply the RAG empty-collection guard.

## Test Attempt 6: RAG Ingestion

Command:

```bash
uv run python -m app.rag.ingest
```

Result:

```text
openai.OpenAIError: The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable
```

## Explanation

This is the same API-key wiring issue that affected `RAGService`.

`app/rag/ingest.py` creates the embedding client as:

```python
OpenAIEmbeddings(model=settings.EMBEDDING_MODEL)
```

but `settings.OPENAI_API_KEY` is loaded by Pydantic and not automatically
exported to `os.environ`. LangChain therefore cannot see the key.

## Fix

Pass the key explicitly:

```python
OpenAIEmbeddings(
    model=settings.EMBEDDING_MODEL,
    api_key=settings.OPENAI_API_KEY,
)
```

Applied. The ingestion command now starts scanning files and reaches the
embedding API:

```text
ingest.scan.started directory=buffett_letters file_count=48
ingest.file.started source_file=2004.pdf year=2004
```

It then fails with the account quota error:

```text
openai.RateLimitError: Error code: 429 - insufficient_quota
```

## Current RAG Status

The source letters are present:

```text
buffett_letters/ -> 48 files
```

The Chroma collection is still empty because embedding generation cannot proceed
with the current OpenAI account quota:

```text
buffett_letters collection count -> 0
```

## RAG Next Step

To create production-like RAG data, the project needs an OpenAI key/account with
available embeddings quota, then rerun:

```bash
uv run python -m app.rag.ingest
```

For local E2E tests without paid OpenAI calls, add a development/mock embedding
mode and a development/mock analysis mode. That would let the backend validate
the full request/response flow without external quota.

## Test Attempt 7: RAG Ingestion After Credits Added

Before running, local `.env` was made explicit about lower-cost models:

```text
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
```

Official pricing check:

- `text-embedding-3-small` is the lowest-cost listed embedding model.
- `gpt-4o-mini` is substantially cheaper than `gpt-4o` for chat analysis.

Command:

```bash
uv run python -m app.rag.ingest
```

Result:

```text
ingest.scan.started directory=buffett_letters file_count=48
ingest.scan.completed total_chunks_ingested=1867
```

Chroma verification:

```text
buffett_letters collection count -> 1867
```

Warning:

Most pre-2004 `.html` files were skipped as `unreadable_content`. A quick file
check shows examples such as `buffett_letters/1977.html` and
`buffett_letters/2003.html` are binary `data`, not readable HTML text:

```text
buffett_letters/1977.html: data
buffett_letters/1984.html: HTML document, Unicode text, UTF-8 text
buffett_letters/2003.html: data
```

The indexed RAG data currently contains the PDF-era letters plus readable HTML
files, totaling 1,867 chunks.

## Test Attempt 8: Full Backend E2E After RAG Ingestion

Backend command:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Startup:

```text
warren_backend.ready rag_service_initialized=True
```

Endpoint results:

```text
GET /health                           -> 200 OK
GET /ready                            -> 200 OK
GET /api/companies                    -> 200 OK
GET /api/companies/WEGE3              -> 200 OK
POST /api/portfolio/analyze           -> 200 OK
POST /api/portfolio/analyze bad total -> 422 Unprocessable Content
POST /api/portfolio/analyze unknown   -> 404 Not Found
POST /api/portfolio/analyze?format=pdf -> 200 OK application/pdf
```

Portfolio analysis request:

```json
{
  "assets": [
    {"ticker": "WEGE3", "type": "STOCK", "percentage": 60},
    {"ticker": "TESOURO", "type": "TESOURO", "percentage": 40}
  ]
}
```

Observed response highlights:

```text
portfolio_grade=B-
WEGE3 score=10.0
WEGE3 verdict=APROVADO
RAG citations returned=1
TESOURO verdict=Capital seguro
alert=OVER_CONCENTRATED
```

Backend logs confirm:

```text
rag.retrieve.completed results=3
openai.call.completed call_type=per_stock score=10.0
openai.call.completed call_type=summary grade=B-
pdf.generation.completed bytes=27700
```

Automated fast test suite:

```bash
uv run pytest -m "not integration"
```

Result:

```text
141 passed, 3 deselected, 1 warning
```

One test isolation issue was fixed: `tests/test_config.py` now passes
`_env_file=None` when asserting class defaults, so local `.env` values such as
`OPENAI_MODEL=gpt-4o-mini` do not override default-value tests.

## Test Attempt 9: Frontend CORS Report

Browser error:

```text
Cross-Origin Request Blocked: The Same Origin Policy disallows reading the
remote resource at http://localhost:8000/api/portfolio/analyze.
Reason: CORS request did not succeed. Status code: (null).
```

Checks against `localhost:8000`:

```bash
curl -v http://localhost:8000/health
```

Result:

```text
Connected to localhost (::1) port 8000
Recv failure: Connection reset by peer
curl: (56) Recv failure: Connection reset by peer
```

Starting this backend on port `8000` fails:

```text
[Errno 98] error while attempting to bind on address ('127.0.0.1', 8000):
address already in use
```

This means another process/container currently owns port `8000`, but it is
resetting HTTP connections.

Control test with this backend on clean port `8001`:

```bash
curl -i -X OPTIONS http://localhost:8001/api/portfolio/analyze \
  -H 'Origin: http://localhost:3000' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type'
```

Result:

```http
HTTP/1.1 200 OK
access-control-allow-methods: GET, POST
access-control-allow-origin: http://localhost:3000
access-control-allow-headers: content-type
```

## Explanation

The FastAPI app's CORS configuration is working for the frontend origin
`http://localhost:3000`.

The frontend error is misleading: `Status code: (null)` and the curl reset show
the browser cannot complete the network request to the service on port `8000`.
The browser reports this under the CORS umbrella because no valid HTTP response
with CORS headers is received.

## Proposed Fix

Stop or restart the broken process/container currently bound to port `8000`,
then start the backend cleanly.

Recommended Docker path from repo root:

```bash
sudo docker compose ps
sudo docker compose logs --tail=100 backend
sudo docker compose restart backend
```

If the backend container keeps failing, run:

```bash
sudo docker compose up backend
```

and inspect the startup error directly.

Alternative local dev path:

```bash
cd warren-backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Then point the frontend API base URL to:

```text
http://localhost:8001
```

No backend CORS code change is proposed yet, because the app returns correct
CORS headers when it is actually reachable.

## Test Attempt 10: Docker Backend Port 8000 Reset

Container log:

```text
OSError: cannot load library 'libgobject-2.0-0':
libgobject-2.0-0: cannot open shared object file: No such file or directory.
...
WeasyPrint could not import some external libraries.
```

Import path:

```text
app/main.py
-> app/routers/portfolio.py
-> app/services/pdf_service.py
-> import weasyprint
-> missing libgobject-2.0-0
```

## Explanation

The browser CORS error is caused by the Docker backend worker crashing at import
time. Uvicorn's reloader parent process keeps port `8000` open, but the actual
ASGI worker fails to start. Requests to `localhost:8000` therefore connect and
then get reset, which browsers report as:

```text
CORS request did not succeed. Status code: (null).
```

This is not a CORS middleware issue.

## Proposed Docker Fix

Install WeasyPrint's required native runtime libraries in
`warren-backend/Dockerfile`.

For the current `python:3.12-slim` Debian image, add before `uv sync`:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
```

Then rebuild and restart:

```bash
sudo docker compose build backend
sudo docker compose up -d backend
curl -i http://localhost:8000/health
```

Also recommended in `docker-compose.yml`: mount the backend's populated RAG data,
not the root-level empty folder:

```yaml
- ./warren-backend/rag_data:/app/rag_data
```

## Status

Waiting for permission to apply the Dockerfile and compose mount fixes.

Applied with permission, but the no-cache Docker build exposed a package-name
issue:

```text
E: Unable to locate package libgobject-2.0-0
E: Couldn't find any package by glob 'libgobject-2.0-0'
```

## Explanation

`libgobject-2.0-0` is the shared library name from the runtime error:

```text
cannot load library 'libgobject-2.0-0'
```

On Debian Bookworm, that shared object is provided by the `libglib2.0-0`
package. It is not installed as a separately named apt package.

## Proposed Fix

Remove `libgobject-2.0-0` from the Dockerfile apt package list and keep
`libglib2.0-0`.

Then rebuild:

```bash
sudo docker compose build --no-cache backend
sudo docker compose up -d backend
curl -i http://localhost:8000/health
```

## Status

Waiting for permission to remove the invalid apt package from the Dockerfile.

Applied with permission: `libgobject-2.0-0` was removed from the apt package
list; `libglib2.0-0` remains.

## Test Attempt 11: Docker Backend Running, Frontend Calls

Container logs now show the backend starts and CORS preflight succeeds:

```text
GET /health HTTP/1.1" 200 OK
OPTIONS /api/portfolio/analyze HTTP/1.1" 200 OK
GET /api/companies HTTP/1.1" 200 OK
```

So the original browser CORS/network failure is fixed.

New failures:

```text
warren_backend.rag_init_failed error='attempt to write a readonly database'
```

and:

```text
POST /api/portfolio/analyze HTTP/1.1" 404 Not Found
tickers=['WEGE3', 'PETR4', 'SAPR3', 'TUPY3']
tickers=['WEGE3', 'PETR4', 'TUPY3', 'VALE3']
```

and:

```text
openai.AuthenticationError: Incorrect API key provided: sk-dummy-key
```

## Explanation

1. Docker is not using the backend `.env` API key.

   `docker-compose.yml` currently has:

   ```yaml
   OPENAI_API_KEY=${OPENAI_API_KEY:-sk-dummy-key}
   ```

   Compose reads interpolation values from the repo-root shell/root `.env`, not
   `warren-backend/.env`. Because the root environment does not provide
   `OPENAI_API_KEY`, the container receives `sk-dummy-key`.

2. ChromaDB cannot write to the mounted RAG SQLite database.

   `warren-backend/rag_data` is owned by host UID/GID `1000:1000`. The Dockerfile
   currently creates `appuser` as UID/GID `1001:1001`. The container can read the
   files but ChromaDB needs SQLite write access for normal startup bookkeeping,
   so RAG initialization fails.

3. The frontend is submitting tickers that are not in the current seed DB.

   Current seed covers:

   ```text
   WEGE3, PETR4, MXRF11, TESOURO
   ```

   Frontend tests/logs include:

   ```text
   SAPR3, TUPY3, VALE3
   ```

## Proposed Fixes

1. Make Docker load `warren-backend/.env`, but keep container-specific overrides
   for DB and Chroma paths:

   ```yaml
   env_file:
     - ./warren-backend/.env
   environment:
     - ENVIRONMENT=development
     - DATABASE_URL=postgresql://${POSTGRES_USER:-warren}:${POSTGRES_PASSWORD:-password}@db:5432/${POSTGRES_DB:-warren}
     - CHROMA_PERSIST_DIR=/app/rag_data
   ```

   Remove the dummy `OPENAI_API_KEY` fallback.

2. Change the Docker app user UID/GID from `1001` to `1000`, matching this host,
   so the container can write the bind-mounted `rag_data` SQLite files.

3. Expand starter seed data with the UI/test tickers:

   ```text
   VALE3, SAPR3, TUPY3
   ```

   Also add a few common base tickers so the frontend suggestion list is less
   sparse:

   ```text
   ITUB4, BBAS3, ABEV3, B3SA3, RENT3, EGIE3, TAEE11
   ```

4. Add/update seed tests to assert the broader base dataset exists and remains
   idempotent.

## Status

Waiting for permission to apply Docker env/user fixes and expand the base seed
dataset.

Applied with permission:

1. `docker-compose.yml`
   - loads `./warren-backend/.env` via `env_file`
   - removes the `sk-dummy-key` fallback
   - mounts `./warren-ingestion/data/cache/b3/tickers.csv` into the backend
   - sets `B3_TICKERS_CSV=/app/data/b3_tickers.csv`
   - runs `uv run python -m app.db.seed` after migrations during backend startup

2. `warren-backend/Dockerfile`
   - changes app user/group to UID/GID `1000:1000` so mounted `rag_data` is writable

3. `app/db/seed.py`
   - loads all B3 ticker company rows from `warren-ingestion/data/cache/b3/tickers.csv`
   - preserves fallback non-B3 assets like `MXRF11` and `TESOURO`
   - keeps financial seed rows for available starter assets

4. `app/services/analysis_service.py`
   - maps `openai.AuthenticationError` to the existing `OpenAIUnavailableError`
     instead of leaking a raw 500 traceback

Validation:

```text
local DB company count -> 527
contains -> MXRF11, PETR4, SAPR3, TESOURO, TUPY3, VALE3, WEGE3
uv run pytest -m "not integration" -q -> 143 passed, 3 deselected, 1 warning
```

Docker rebuild required:

```bash
sudo docker compose build --no-cache backend
sudo docker compose up -d --force-recreate backend
curl -i http://localhost:8000/ready
```

## Test Attempt 12: Full B3 Company Metadata But Missing Financials

Frontend request logs:

```text
tickers=['WEGE3', 'SAPR3', 'ALPA3', 'ITUB3', 'BBDC3']
POST /api/portfolio/analyze HTTP/1.1" 404 Not Found
```

DB verification:

```text
WEGE3 company=True financial=True
SAPR3 company=True financial=False
ALPA3 company=True financial=False
ITUB3 company=True financial=False
BBDC3 company=True financial=False
```

## Explanation

The B3 ingestion cache provides ticker/company metadata:

```text
ticker, name, sector, segment, asset_type
```

It does not provide the annual financial fundamentals required by the current
stock analysis path:

```text
roe, lucro_liquido, margem_liquida, receita_liquida, divida_liquida,
ebitda, divida_ebitda, market_cap, p_l, cagr_lucro
```

So the DB now has broad autocomplete coverage, but only the starter financial
rows have analysis-ready fundamentals. The current `PortfolioService` raises
`TickerNotFoundError` when financials are missing, which returns a misleading
404 even though the ticker exists.

## Proposed Fix

Do not create fake financial rows for every B3 ticker. That would make the
analysis look more complete than the data really is.

Instead:

1. Keep all B3 company rows for frontend autocomplete.
2. Change portfolio analysis so stocks with no financial data return a degraded
   stock response:

   ```text
   score=0
   verdict="Dados financeiros indisponíveis"
   financials={all metrics null}
   buffett_verdict="Ainda não temos fundamentos suficientes..."
   ```

3. Continue analyzing the rest of the portfolio instead of failing the whole
   request with 404.
4. Reserve 404 for tickers truly absent from `companies`.

This lets the frontend submit any B3 ticker while making the data limitation
explicit in the response.

## Status

Waiting for permission to implement graceful missing-financials handling.

Applied with permission.

Implementation:

- Existing companies with no `financials` row now return a degraded
  `StockAssetResponse` instead of raising `TickerNotFoundError`.
- The response uses:

```text
score=0.0
verdict="Dados financeiros indisponíveis"
financials={all metrics null}
buffett_citations=[]
```

- RAG and per-stock OpenAI analysis are skipped for that asset.
- True 404 remains reserved for tickers absent from the `companies` table.

Validation:

```text
tests/services/test_portfolio_service.py -> 21 passed
uv run pytest -m "not integration" -q -> 143 passed, 3 deselected, 1 warning
```

Live Docker check immediately after patch still returned:

```http
HTTP/1.1 404 Not Found
{"detail":"Ticker SAPR3 not found in database"}
```

That response is the old container behavior. The running Docker backend needs to
be restarted/recreated so Uvicorn loads the patched bind-mounted code.

Required command:

```bash
sudo docker compose up -d --force-recreate backend
```

Then retest the same frontend portfolio.
