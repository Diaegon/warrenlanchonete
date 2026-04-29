"""GPT-4o analysis service for Warren Lanchonete backend.

AnalysisService handles all OpenAI chat completions calls. It provides:
    - analyze_stock: Per-stock Buffett-style analysis with scoring rubric
    - generate_portfolio_summary: Portfolio-level grade and narrative

Both methods use JSON mode (response_format={"type": "json_object"}) so
responses are parsed directly into Pydantic models.

Legal compliance:
    The system prompts explicitly prohibit directive language per CVM guidelines.
    The forbidden words list ("recomendamos", "sugerimos", etc.) is enforced in
    the system prompt, not left to chance.

Error handling:
    - openai.APIConnectionError → OpenAIUnavailableError (HTTP 503)
    - openai.APITimeoutError → OpenAIUnavailableError (HTTP 503)
    - json.JSONDecodeError → OpenAIUnavailableError (HTTP 503)
"""
from __future__ import annotations

import json
import time
from typing import Any

import openai
import structlog
import structlog.contextvars
from pydantic import BaseModel, field_validator

from app.exceptions import OpenAIUnavailableError
from app.metrics import openai_calls_total, openai_duration_seconds
from app.schemas.portfolio import BuffettCitation, PortfolioGrade

logger = structlog.get_logger(__name__)


# ── Internal Pydantic models (not exported as API schemas) ────────────────────

class StockAnalysis(BaseModel):
    """Result of per-stock Buffett analysis from GPT-4o."""

    score: float
    verdict: str
    buffett_verdict: str
    buffett_citations: list[BuffettCitation]
    retail_adaptation_note: str


class PortfolioSummary(BaseModel):
    """Portfolio-level grade and narrative from GPT-4o."""

    portfolio_grade: PortfolioGrade
    portfolio_summary: str

    @field_validator("portfolio_grade", mode="before")
    @classmethod
    def strip_grade_whitespace(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v


# ── System Prompts ─────────────────────────────────────────────────────────────

_STOCK_SYSTEM_PROMPT = """You are the Warren Lanchonete analysis engine — a financial analyst with deep knowledge \
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
- Buffett managed billions of dollars — many of his criteria (e.g. moat requiring market \
dominance at global scale) must be adapted for a retail investor with a diversified \
portfolio of R$ 10k–500k
- Always include a "retail_adaptation_note" that contextualizes Buffett's standard for \
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
}"""

_SUMMARY_SYSTEM_PROMPT = """You are the Warren Lanchonete portfolio grader.

LEGAL RULES:
- NEVER use: "recomendamos", "sugerimos", "você deve", "é recomendado", "aconselhamos"
- This is a portfolio composition analysis, not investment advice
- Frame all findings as observations, not instructions

TONE: Brazilian Portuguese, ironic, direct, slightly humorous.

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
}"""


# ── Service ───────────────────────────────────────────────────────────────────

class AnalysisService:
    """GPT-4o powered analysis service for stocks and portfolio summaries.

    Args:
        api_key: OpenAI API key.
        model: OpenAI model identifier (e.g. 'gpt-4o').
        timeout: Request timeout in seconds.
    """

    def __init__(self, api_key: str, model: str, timeout: int) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._model = model

    async def analyze_stock(
        self,
        company: Any,
        financials: Any,
        citations: list[BuffettCitation],
    ) -> StockAnalysis:
        """Analyze a single stock using Buffett's investment philosophy.

        Constructs a prompt from company data, financials, and RAG citations,
        then calls GPT-4o with JSON mode to produce a structured analysis.

        Args:
            company: Company ORM object with name, ticker, sector attributes.
            financials: Financial ORM object with year, roe, margem_liquida,
                cagr_lucro, divida_ebitda attributes.
            citations: List of BuffettCitation from RAGService.retrieve().

        Returns:
            StockAnalysis with score, verdict, narrative, and citations.

        Raises:
            OpenAIUnavailableError: On APIConnectionError, APITimeoutError, or
                invalid JSON response from OpenAI.
        """
        # Format citations for prompt
        if citations:
            formatted_citations = "\n".join(
                f'[{c.year}] "{c.passage}"' for c in citations
            )
        else:
            formatted_citations = "None retrieved. Assess the company based on financials alone."

        user_prompt = (
            f"Analyze the following Brazilian company from Warren Buffett's perspective:\n\n"
            f"COMPANY: {company.name} ({company.ticker})\n"
            f"SECTOR: {company.sector}\n"
            f"LATEST FINANCIALS ({financials.year}):\n"
            f"- ROE: {financials.roe}%\n"
            f"- Net margin: {financials.margem_liquida}%\n"
            f"- 5-year profit CAGR: {financials.cagr_lucro}%\n"
            f"- Debt/EBITDA: {financials.divida_ebitda}x\n\n"
            f"BUFFETT PASSAGES (retrieved from his shareholder letters — use these as citations):\n"
            f"{formatted_citations}\n\n"
            f"Apply the scoring rubric. Explain the score. Cite the most relevant passage.\n"
            f"If no passage is highly relevant, say so in the relevance field."
        )

        logger.info("openai.call.started", call_type="per_stock", ticker=company.ticker)
        openai_calls_total.labels(call_type="per_stock").inc()
        start = time.monotonic()

        trace_id = structlog.contextvars.get_contextvars().get("trace_id", "")

        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _STOCK_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                extra_headers={"X-Request-ID": trace_id} if trace_id else {},
            )
            elapsed = time.monotonic() - start
            openai_duration_seconds.labels(call_type="per_stock").observe(elapsed)

            content = completion.choices[0].message.content
            data = json.loads(content)
            result = StockAnalysis(**data)

            logger.info(
                "openai.call.completed",
                call_type="per_stock",
                ticker=company.ticker,
                score=result.score,
                elapsed=elapsed,
            )
            return result

        except (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError) as exc:
            elapsed = time.monotonic() - start
            logger.error(
                "openai.call.failed",
                call_type="per_stock",
                ticker=company.ticker,
                error=str(exc),
                elapsed=elapsed,
            )
            raise OpenAIUnavailableError(str(exc)) from exc

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            elapsed = time.monotonic() - start
            logger.error(
                "openai.call.parse_failed",
                call_type="per_stock",
                ticker=company.ticker,
                error=str(exc),
                elapsed=elapsed,
            )
            raise OpenAIUnavailableError(f"Failed to parse OpenAI response: {exc}") from exc

    async def generate_portfolio_summary(
        self,
        assets: list[Any],
        alerts: list[Any],
    ) -> PortfolioSummary:
        """Generate a portfolio-level grade and narrative summary.

        Args:
            assets: List of asset response objects (StockAssetResponse, etc.).
            alerts: List of PortfolioAlert objects detected by PortfolioService.

        Returns:
            PortfolioSummary with portfolio_grade and portfolio_summary.

        Raises:
            OpenAIUnavailableError: On APIConnectionError, APITimeoutError, or
                invalid JSON response from OpenAI.
        """
        # Build asset lines for the prompt
        asset_lines: list[str] = []
        for asset in assets:
            asset_type = getattr(asset, "type", "UNKNOWN")
            if asset_type == "STOCK":
                asset_lines.append(
                    f"- {asset.ticker}: score={asset.score}, verdict={asset.verdict}, "
                    f"sector={asset.sector}, {asset.percentage}%"
                )
            elif asset_type == "FII":
                asset_lines.append(f"- {asset.ticker}: FII, {asset.percentage}% — deep analysis pending")
            else:  # TESOURO
                asset_lines.append(f"- {asset.ticker}: TESOURO, {asset.percentage}% — safe capital")

        assets_text = "\n".join(asset_lines) if asset_lines else "No assets provided."

        if alerts:
            alerts_text = "\n".join(
                f"- {a.type}: {a.message}" for a in alerts
            )
        else:
            alerts_text = "none"

        user_prompt = (
            f"Grade this portfolio:\n\n"
            f"ASSETS:\n{assets_text}\n\n"
            f"ALERTS DETECTED: {alerts_text}\n\n"
            f"Consider: diversification, quality of stock picks, presence of safe capital buffer,\n"
            f"concentration risk, sector overlap.\n\n"
            f"Apply the grading scale. Write the summary in Brazilian Portuguese."
        )

        logger.info("openai.call.started", call_type="summary")
        openai_calls_total.labels(call_type="summary").inc()
        start = time.monotonic()

        trace_id = structlog.contextvars.get_contextvars().get("trace_id", "")

        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                extra_headers={"X-Request-ID": trace_id} if trace_id else {},
            )
            elapsed = time.monotonic() - start
            openai_duration_seconds.labels(call_type="summary").observe(elapsed)

            content = completion.choices[0].message.content
            data = json.loads(content)
            result = PortfolioSummary(**data)

            logger.info(
                "openai.call.completed",
                call_type="summary",
                grade=result.portfolio_grade,
                elapsed=elapsed,
            )
            return result

        except (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError) as exc:
            elapsed = time.monotonic() - start
            logger.error(
                "openai.call.failed",
                call_type="summary",
                error=str(exc),
                elapsed=elapsed,
            )
            raise OpenAIUnavailableError(str(exc)) from exc

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            elapsed = time.monotonic() - start
            logger.error(
                "openai.call.parse_failed",
                call_type="summary",
                error=str(exc),
                elapsed=elapsed,
            )
            raise OpenAIUnavailableError(f"Failed to parse OpenAI response: {exc}") from exc
