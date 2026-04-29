"""Pydantic v2 schemas for company and financial history API responses.

Used by GET /api/companies and GET /api/companies/{ticker}.
"""

from pydantic import BaseModel, ConfigDict


class CompanySchema(BaseModel):
    """Company listing schema for GET /api/companies.

    Attributes:
        ticker: B3 ticker symbol.
        name: Full company name.
        sector: B3 sector classification.
        segment: B3 segment within the sector.
        asset_type: 'STOCK' or 'FII'.
    """

    ticker: str
    name: str
    sector: str | None
    segment: str | None
    asset_type: str

    model_config = ConfigDict(from_attributes=True)


class FinancialHistoryItem(BaseModel):
    """Annual financial data item for GET /api/companies/{ticker}.

    All numeric fields are float | None because Numeric columns in PostgreSQL
    serialize as Decimal — we expose them as float for JSON compatibility.

    Attributes:
        year: Fiscal year.
        roe: Return on equity as percentage.
        lucro_liquido: Net profit in BRL.
        margem_liquida: Net margin as percentage.
        receita_liquida: Net revenue in BRL.
        divida_liquida: Net debt in BRL.
        ebitda: EBITDA in BRL.
        divida_ebitda: Net debt / EBITDA ratio.
        market_cap: Market capitalization in BRL.
        p_l: Price-to-earnings ratio.
        cagr_lucro: 5-year profit CAGR as percentage.
    """

    year: int
    roe: float | None
    lucro_liquido: float | None
    margem_liquida: float | None
    receita_liquida: float | None
    divida_liquida: float | None
    ebitda: float | None
    divida_ebitda: float | None
    market_cap: float | None
    p_l: float | None
    cagr_lucro: float | None

    model_config = ConfigDict(from_attributes=True)


class CompanyDetailSchema(CompanySchema):
    """Detailed company schema with full financial history.

    Extends CompanySchema with a list of annual financial records.

    Attributes:
        financials: List of annual financial data, ordered by year descending.
    """

    financials: list[FinancialHistoryItem]

    model_config = ConfigDict(from_attributes=True)
