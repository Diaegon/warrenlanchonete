"""FastAPI application factory for Warren Lanchonete backend.

Creates and configures the FastAPI application with:
- Lifespan context manager for startup/shutdown
- CORS middleware
- Request ID middleware with structlog context
- Exception handlers for domain exceptions
- Router registration under /api prefix
- Health and readiness endpoints
- Prometheus instrumentation
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.config import settings
from app.db.session import engine
from app.exceptions import OpenAIUnavailableError, PDFGenerationError, TickerNotFoundError
from app.logging_config import configure_logging
from app.routers.companies import router as companies_router
from app.routers.portfolio import router as portfolio_router

logger = structlog.get_logger(__name__)

# ContextVar for request-scoped trace ID
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle.

    Startup:
        - Configure structlog
        - Initialize ChromaDB client (placeholder until AI agent implements)
        - Store rag_service in app.state (None for now)

    Shutdown:
        - Dispose SQLAlchemy engine connection pool
    """
    # Configure structured logging
    env = settings.ENVIRONMENT if settings is not None else "development"
    log_level = settings.LOG_LEVEL if settings is not None else "INFO"
    configure_logging(environment=env, log_level=log_level)

    logger.info("warren_backend.startup", environment=env)

    # ChromaDB and RAGService initialization
    try:
        import chromadb as _chromadb
        from app.rag.client import get_chroma_client
        from app.services.rag_service import RAGService

        chroma_client = get_chroma_client()
        app.state.chroma_client = chroma_client
        app.state.rag_service = RAGService(chroma_client=chroma_client)
        logger.info("warren_backend.ready", rag_service_initialized=True)
    except Exception as exc:
        # Graceful degradation: if ChromaDB or settings are unavailable (e.g. test env),
        # start without RAG service — /ready endpoint will reflect degraded state
        app.state.chroma_client = None
        app.state.rag_service = None
        logger.warning("warren_backend.rag_init_failed", error=str(exc), rag_service_initialized=False)

    yield

    # Shutdown: dispose DB engine
    await engine.dispose()
    logger.info("warren_backend.shutdown")


# ── App Factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    lifespan=lifespan,
    title="Warren Lanchonete",
    description="Brazilian portfolio analyzer powered by Buffett's investment philosophy",
    version="0.1.0",
)


# ── CORS Middleware ───────────────────────────────────────────────────────────

_cors_origins = (
    settings.CORS_ORIGINS.split(",")
    if settings is not None
    else ["http://localhost:3000"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Request ID Middleware ─────────────────────────────────────────────────────

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Generate a UUID4 request ID per request and inject into structlog context.

    The request ID is stored in a ContextVar so all log entries within the
    same request include the same trace_id, enabling log correlation.
    """
    request_id = str(uuid.uuid4())
    _request_id_var.set(request_id)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        trace_id=request_id,
        service="warren-backend",
        environment=settings.ENVIRONMENT if settings is not None else "development",
    )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Exception Handlers ────────────────────────────────────────────────────────

@app.exception_handler(TickerNotFoundError)
async def ticker_not_found_handler(request: Request, exc: TickerNotFoundError) -> JSONResponse:
    """Handle TickerNotFoundError → 404."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(OpenAIUnavailableError)
async def openai_unavailable_handler(request: Request, exc: OpenAIUnavailableError) -> JSONResponse:
    """Handle OpenAIUnavailableError → 503."""
    return JSONResponse(
        status_code=503,
        content={"detail": "Analysis service temporarily unavailable. Try again in a moment."},
    )


@app.exception_handler(PDFGenerationError)
async def pdf_error_handler(request: Request, exc: PDFGenerationError) -> JSONResponse:
    """Handle PDFGenerationError → 500."""
    return JSONResponse(status_code=500, content={"detail": "PDF generation failed"})


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(portfolio_router, prefix="/api")
app.include_router(companies_router, prefix="/api")


# ── Health & Readiness Endpoints ──────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Health check — always returns 200 if the process is running.

    Returns:
        JSON with status "ok".
    """
    return {"status": "ok"}


@app.get("/ready", tags=["ops"])
async def ready(request: Request) -> JSONResponse:
    """Readiness check — verifies DB connectivity and ChromaDB availability.

    Returns:
        200 {"status": "ok"} if both DB and ChromaDB are available.
        503 {"status": "degraded", "detail": "..."} if either check fails.
    """
    issues: list[str] = []

    # DB check
    try:
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        issues.append(f"DB unavailable: {exc}")

    # ChromaDB check
    chroma_client = getattr(request.app.state, "chroma_client", None)
    if chroma_client is None:
        issues.append("ChromaDB not initialized")
    else:
        try:
            collection = chroma_client.get_collection("buffett_letters")
            if collection.count() == 0:
                issues.append(
                    "ChromaDB collection 'buffett_letters' is empty — "
                    "run: uv run python -m app.rag.ingest"
                )
        except Exception as exc:
            issues.append(f"ChromaDB collection unavailable: {exc}")

    if issues:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "detail": "; ".join(issues)},
        )

    return JSONResponse(status_code=200, content={"status": "ok"})


# ── Prometheus Instrumentation ────────────────────────────────────────────────

Instrumentator().instrument(app).expose(app)
