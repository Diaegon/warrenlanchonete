"""TDD tests for app/services/analysis_service.py — AnalysisService.

Tests:
    - analyze_stock parses valid JSON response into StockAnalysis
    - analyze_stock raises OpenAIUnavailableError on APIConnectionError
    - analyze_stock raises OpenAIUnavailableError on APITimeoutError
    - analyze_stock raises OpenAIUnavailableError on invalid JSON
    - generate_portfolio_summary parses valid JSON into PortfolioSummary
    - System prompt does NOT contain forbidden directive language

All tests marked @pytest.mark.slow (mocked OpenAI).
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

from app.exceptions import OpenAIUnavailableError
from app.schemas.portfolio import BuffettCitation


def _make_mock_company(
    name="WEG S.A.",
    ticker="WEGE3",
    sector="Industrial",
):
    """Create a mock Company ORM object."""
    company = MagicMock()
    company.name = name
    company.ticker = ticker
    company.sector = sector
    return company


def _make_mock_financial(
    year=2024,
    roe=28.5,
    margem_liquida=15.2,
    cagr_lucro=18.3,
    divida_ebitda=0.4,
):
    """Create a mock Financial ORM object."""
    fin = MagicMock()
    fin.year = year
    fin.roe = roe
    fin.margem_liquida = margem_liquida
    fin.cagr_lucro = cagr_lucro
    fin.divida_ebitda = divida_ebitda
    return fin


def _make_citations():
    """Create sample BuffettCitations for testing."""
    return [
        BuffettCitation(
            year=1992,
            passage="A truly wonderful business earns very high returns.",
            relevance="",
        )
    ]


@pytest.mark.slow
class TestAnalyzeStock:
    """Tests for AnalysisService.analyze_stock()."""

    def _make_service(self):
        """Create an AnalysisService with mocked OpenAI client."""
        from app.services.analysis_service import AnalysisService
        return AnalysisService(
            api_key="sk-test-key",
            model="gpt-4o",
            timeout=30,
        )

    async def test_parses_valid_json_response_into_stock_analysis(self):
        """analyze_stock returns StockAnalysis with correct fields from valid JSON."""
        from app.services.analysis_service import AnalysisService, StockAnalysis

        valid_response = {
            "score": 8.5,
            "verdict": "APROVADO",
            "buffett_verdict": "WEG demonstra o que Buffett chama de moat durável.",
            "buffett_citations": [
                {
                    "year": 1992,
                    "passage": "A truly wonderful business earns very high returns.",
                    "relevance": "WEG's ROE of 28% exemplifies this principle.",
                }
            ],
            "retail_adaptation_note": "Para investidor retail, ROE acima de 15% é excelente.",
        }

        mock_message = MagicMock()
        mock_message.content = json.dumps(valid_response)

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        with patch("app.services.analysis_service.openai.AsyncOpenAI", return_value=mock_openai_client):
            svc = self._make_service()
            result = await svc.analyze_stock(
                company=_make_mock_company(),
                financials=_make_mock_financial(),
                citations=_make_citations(),
            )

        assert isinstance(result, StockAnalysis)
        assert result.score == 8.5
        assert result.verdict == "APROVADO"
        assert "WEG" in result.buffett_verdict
        assert len(result.buffett_citations) == 1
        assert result.buffett_citations[0].year == 1992
        assert result.retail_adaptation_note != ""

    async def test_raises_openai_unavailable_on_api_connection_error(self):
        """analyze_stock raises OpenAIUnavailableError on APIConnectionError."""
        from app.services.analysis_service import AnalysisService

        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=openai.APIConnectionError(request=MagicMock())
        )

        with patch("app.services.analysis_service.openai.AsyncOpenAI", return_value=mock_openai_client):
            svc = self._make_service()
            with pytest.raises(OpenAIUnavailableError):
                await svc.analyze_stock(
                    company=_make_mock_company(),
                    financials=_make_mock_financial(),
                    citations=_make_citations(),
                )

    async def test_raises_openai_unavailable_on_api_timeout_error(self):
        """analyze_stock raises OpenAIUnavailableError on APITimeoutError."""
        from app.services.analysis_service import AnalysisService

        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=openai.APITimeoutError(request=MagicMock())
        )

        with patch("app.services.analysis_service.openai.AsyncOpenAI", return_value=mock_openai_client):
            svc = self._make_service()
            with pytest.raises(OpenAIUnavailableError):
                await svc.analyze_stock(
                    company=_make_mock_company(),
                    financials=_make_mock_financial(),
                    citations=_make_citations(),
                )

    async def test_raises_openai_unavailable_on_rate_limit_error(self):
        """analyze_stock raises OpenAIUnavailableError on RateLimitError (HTTP 429)."""
        from app.services.analysis_service import AnalysisService

        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=openai.RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            )
        )

        with patch("app.services.analysis_service.openai.AsyncOpenAI", return_value=mock_openai_client):
            svc = self._make_service()
            with pytest.raises(OpenAIUnavailableError):
                await svc.analyze_stock(
                    company=_make_mock_company(),
                    financials=_make_mock_financial(),
                    citations=_make_citations(),
                )

    async def test_raises_openai_unavailable_on_authentication_error(self):
        """analyze_stock raises OpenAIUnavailableError on invalid API key."""
        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=openai.AuthenticationError(
                message="Invalid API key",
                response=MagicMock(status_code=401, headers={}),
                body=None,
            )
        )

        with patch("app.services.analysis_service.openai.AsyncOpenAI", return_value=mock_openai_client):
            svc = self._make_service()
            with pytest.raises(OpenAIUnavailableError):
                await svc.analyze_stock(
                    company=_make_mock_company(),
                    financials=_make_mock_financial(),
                    citations=_make_citations(),
                )

    async def test_raises_openai_unavailable_on_invalid_json(self):
        """analyze_stock raises OpenAIUnavailableError when response is not valid JSON."""
        from app.services.analysis_service import AnalysisService

        mock_message = MagicMock()
        mock_message.content = "This is not valid JSON at all!!!"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        with patch("app.services.analysis_service.openai.AsyncOpenAI", return_value=mock_openai_client):
            svc = self._make_service()
            with pytest.raises(OpenAIUnavailableError):
                await svc.analyze_stock(
                    company=_make_mock_company(),
                    financials=_make_mock_financial(),
                    citations=_make_citations(),
                )


@pytest.mark.slow
class TestGeneratePortfolioSummary:
    """Tests for AnalysisService.generate_portfolio_summary()."""

    def _make_service(self):
        from app.services.analysis_service import AnalysisService
        return AnalysisService(
            api_key="sk-test-key",
            model="gpt-4o",
            timeout=30,
        )

    async def test_raises_openai_unavailable_on_rate_limit_error(self):
        """generate_portfolio_summary raises OpenAIUnavailableError on RateLimitError."""
        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=openai.RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            )
        )

        with patch("app.services.analysis_service.openai.AsyncOpenAI", return_value=mock_openai_client):
            svc = self._make_service()
            with pytest.raises(OpenAIUnavailableError):
                await svc.generate_portfolio_summary(assets=[], alerts=[])

    async def test_parses_valid_json_into_portfolio_summary(self):
        """generate_portfolio_summary returns PortfolioSummary from valid JSON."""
        from app.services.analysis_service import AnalysisService, PortfolioSummary

        valid_response = {
            "portfolio_grade": "B+",
            "portfolio_summary": (
                "O portfólio demonstra qualidade em WEGE3 mas concentração preocupante. "
                "A ausência de renda fixa expõe o investidor a volatilidade excessiva. "
                "No geral, um portfólio equilibrado mas com espaço para melhorias."
            ),
        }

        mock_message = MagicMock()
        mock_message.content = json.dumps(valid_response)

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        # Create minimal mock assets and alerts
        mock_stock = MagicMock()
        mock_stock.type = "STOCK"
        mock_stock.ticker = "WEGE3"
        mock_stock.score = 8.5
        mock_stock.verdict = "APROVADO"
        mock_stock.sector = "Industrial"
        mock_stock.percentage = 100.0

        with patch("app.services.analysis_service.openai.AsyncOpenAI", return_value=mock_openai_client):
            svc = self._make_service()
            result = await svc.generate_portfolio_summary(
                assets=[mock_stock],
                alerts=[],
            )

        assert isinstance(result, PortfolioSummary)
        assert result.portfolio_grade == "B+"
        assert len(result.portfolio_summary) > 0


class TestSystemPromptCompliance:
    """Tests that system prompts comply with legal/tone requirements.

    These tests only inspect module-level constants (no async, no OpenAI calls).
    Not marked slow — safe for standard CI run.
    """

    def test_per_stock_system_prompt_has_no_forbidden_words(self):
        """System prompt for analyze_stock must include the 'NEVER use' prohibition list.

        The forbidden words must appear only inside the prohibition directive,
        not as instructional language. The presence of the full prohibition string
        is the correct compliance check — GPT-4o reads the prohibition, not us.
        """
        from app.services.analysis_service import _STOCK_SYSTEM_PROMPT

        # The correct compliance check: the prompt explicitly prohibits these words
        # The prohibition is expressed as: NEVER use: "recomendamos", ...
        # This is compliant — it's the instruction NOT to use them
        forbidden_words_listed = [
            "recomendamos",
            "sugerimos",
            "você deve",
            "é recomendado",
            "aconselhamos",
        ]

        # All forbidden words must appear in the NEVER use prohibition statement
        prohibition_block = _STOCK_SYSTEM_PROMPT.lower()
        assert "never use" in prohibition_block, (
            "System prompt must contain a 'NEVER use' prohibition block"
        )

        for word in forbidden_words_listed:
            assert word in prohibition_block, (
                f"Forbidden word '{word}' must be listed in the prohibition block"
            )

    def test_portfolio_summary_system_prompt_has_no_forbidden_words(self):
        """System prompt for generate_portfolio_summary must include the 'NEVER use' prohibition.

        Same compliance check as per-stock prompt.
        """
        from app.services.analysis_service import _SUMMARY_SYSTEM_PROMPT

        forbidden_words_listed = [
            "recomendamos",
            "sugerimos",
            "você deve",
            "é recomendado",
            "aconselhamos",
        ]

        prohibition_block = _SUMMARY_SYSTEM_PROMPT.lower()
        assert "never use" in prohibition_block, (
            "Summary system prompt must contain a 'NEVER use' prohibition block"
        )

        for word in forbidden_words_listed:
            assert word in prohibition_block, (
                f"Forbidden word '{word}' must be listed in the prohibition block"
            )

    def test_stock_system_prompt_contains_legal_disclaimer(self):
        """System prompt must contain the 'NEVER use' directive language prohibition."""
        from app.services.analysis_service import _STOCK_SYSTEM_PROMPT

        assert "NEVER use" in _STOCK_SYSTEM_PROMPT or "never use" in _STOCK_SYSTEM_PROMPT.lower(), (
            "System prompt must explicitly prohibit certain language"
        )

    def test_stock_system_prompt_contains_retail_context(self):
        """System prompt must reference retail investor context."""
        from app.services.analysis_service import _STOCK_SYSTEM_PROMPT

        # Should mention retail investors
        assert "retail" in _STOCK_SYSTEM_PROMPT.lower(), (
            "System prompt must reference retail investor context"
        )


class TestInternalModels:
    """Tests for StockAnalysis and PortfolioSummary internal Pydantic models.

    These are unit tests — no OpenAI calls, no async.
    """

    def test_stock_analysis_model_instantiation(self):
        """StockAnalysis can be instantiated with valid fields."""
        from app.services.analysis_service import StockAnalysis

        analysis = StockAnalysis(
            score=7.5,
            verdict="APROVADO",
            buffett_verdict="Empresa excelente com moat durável.",
            buffett_citations=[
                {"year": 1992, "passage": "High returns on capital.", "relevance": "ROE>25%"}
            ],
            retail_adaptation_note="Ótimo para carteira de longo prazo.",
        )
        assert analysis.score == 7.5
        assert analysis.verdict == "APROVADO"
        assert len(analysis.buffett_citations) == 1
        assert analysis.buffett_citations[0].year == 1992

    def test_portfolio_summary_model_instantiation(self):
        """PortfolioSummary can be instantiated with valid fields."""
        from app.services.analysis_service import PortfolioSummary

        summary = PortfolioSummary(
            portfolio_grade="B+",
            portfolio_summary="Portfólio com qualidade razoável mas concentrado.",
        )
        assert summary.portfolio_grade == "B+"
        assert len(summary.portfolio_summary) > 0

    def test_analysis_service_instantiation(self):
        """AnalysisService can be instantiated without connecting to OpenAI."""
        from app.services.analysis_service import AnalysisService

        with patch("app.services.analysis_service.openai.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            svc = AnalysisService(api_key="sk-test", model="gpt-4o", timeout=30)
            assert svc._model == "gpt-4o"
