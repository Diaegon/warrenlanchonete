"""Pydantic v2 schemas for portfolio analysis request and response.

These schemas define the API contract for POST /api/portfolio/analyze.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class AssetType(str, Enum):
    """Supported asset types in Warren Lanchonete."""

    STOCK = "STOCK"
    FII = "FII"
    TESOURO = "TESOURO"


class AssetInput(BaseModel):
    """Single asset in a portfolio analysis request.

    Attributes:
        ticker: B3 ticker symbol (e.g. 'WEGE3'). Max 10 chars.
        type: Asset type — STOCK, FII, or TESOURO.
        percentage: Portfolio allocation percentage. Must be > 0 and <= 100.
    """

    ticker: str = Field(..., min_length=1, max_length=10)
    type: AssetType
    percentage: float = Field(..., gt=0, le=100)


class PortfolioRequest(BaseModel):
    """Portfolio analysis request with percentage sum validation.

    Attributes:
        assets: Non-empty list of assets. Percentages must sum to 100 (tolerance 0.01).
    """

    assets: list[AssetInput] = Field(..., min_length=1)

    @model_validator(mode="after")
    def percentages_must_sum_to_100(self) -> "PortfolioRequest":
        """Validate that all asset percentages sum to 100.

        Raises:
            ValueError: If the sum deviates from 100 by more than 0.01.

        Returns:
            Self if validation passes.
        """
        total = sum(a.percentage for a in self.assets)
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Asset percentages must sum to 100, got {total:.4f}")
        return self


# ─── Response Schemas ─────────────────────────────────────────────────────────


class BuffettCitation(BaseModel):
    """A passage from Buffett's shareholder letters with relevance annotation.

    Attributes:
        year: Year of the shareholder letter (e.g. 1992).
        passage: Exact passage text retrieved from ChromaDB.
        relevance: GPT-4o explanation of why this passage applies to this company.
    """

    year: int
    passage: str
    relevance: str


class FinancialSnapshot(BaseModel):
    """Key financial metrics for a stock at the time of analysis.

    All fields are optional — some companies may not have all metrics available.

    Attributes:
        roe: Return on equity as percentage.
        margem_liquida: Net margin as percentage.
        cagr_lucro: 5-year profit CAGR as percentage.
        divida_ebitda: Net debt / EBITDA ratio.
    """

    roe: float | None
    margem_liquida: float | None
    cagr_lucro: float | None
    divida_ebitda: float | None


class StockAssetResponse(BaseModel):
    """Full analysis response for a STOCK asset.

    Attributes:
        ticker: B3 ticker symbol.
        company_name: Full company name from the database.
        sector: B3 sector classification.
        type: Discriminator literal — always "STOCK".
        percentage: Portfolio allocation percentage.
        score: Buffett score 0.0–10.0 computed by AnalysisService.
        verdict: Human-readable verdict — APROVADO, ATENÇÃO, or REPROVADO.
        financials: Key financial metrics snapshot.
        buffett_verdict: 2–3 sentence analysis in Brazilian Portuguese.
        buffett_citations: Relevant Buffett letter passages with relevance notes.
        retail_adaptation_note: Contextualizes Buffett's criteria for retail investors.
    """

    ticker: str
    company_name: str
    sector: str | None
    type: Literal["STOCK"]
    percentage: float
    score: float
    verdict: str
    financials: FinancialSnapshot
    buffett_verdict: str
    buffett_citations: list[BuffettCitation]
    retail_adaptation_note: str


class FIIAssetResponse(BaseModel):
    """Minimal response for a FII (real estate fund) asset.

    Deep analysis is out of scope for v1 — FIIs get a fixed informational verdict.

    Attributes:
        ticker: B3 ticker symbol.
        type: Discriminator literal — always "FII".
        percentage: Portfolio allocation percentage.
        verdict: Fixed informational text.
    """

    ticker: str
    type: Literal["FII"]
    percentage: float
    verdict: str = "FII — análise detalhada em breve"


class TesouroAssetResponse(BaseModel):
    """Minimal response for a TESOURO (government bond) asset.

    Attributes:
        ticker: Ticker/label for the tesouro position.
        type: Discriminator literal — always "TESOURO".
        percentage: Portfolio allocation percentage.
        verdict: Fixed "Capital seguro" text.
    """

    ticker: str
    type: Literal["TESOURO"]
    percentage: float
    verdict: str = "Capital seguro"


# Discriminated union — Pydantic uses the 'type' field to determine which model to use
AssetResponse = Annotated[
    StockAssetResponse | FIIAssetResponse | TesouroAssetResponse,
    Field(discriminator="type"),
]


class AlertType(str, Enum):
    """Types of portfolio alerts detected by the tone-of-voice trigger system."""

    TESOURO_LOW = "TESOURO_LOW"
    TESOURO_ZERO = "TESOURO_ZERO"
    SINGLE_STOCK_100 = "SINGLE_STOCK_100"
    COMMODITY_HEAVY = "COMMODITY_HEAVY"
    OVER_CONCENTRATED = "OVER_CONCENTRATED"


class PortfolioAlert(BaseModel):
    """A portfolio alert with a pre-written humorous message.

    Attributes:
        type: Alert type enum.
        message: Pre-written phrase for this alert (brand voice).
    """

    type: AlertType
    message: str


class PortfolioResponse(BaseModel):
    """Complete portfolio analysis response.

    Attributes:
        portfolio_grade: Letter grade A–F assigned by AnalysisService.
        portfolio_summary: 3–5 sentence narrative in Brazilian Portuguese.
        portfolio_alerts: List of tone-of-voice alerts detected.
        assets: Per-asset analysis results (discriminated union by type).
    """

    portfolio_grade: str
    portfolio_summary: str
    portfolio_alerts: list[PortfolioAlert]
    assets: list[AssetResponse]
