"""SQLAlchemy ORM model for the financials table."""
from sqlalchemy import Column, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.session import Base


class Financial(Base):
    """ORM model for annual financial data of a company.

    One row per company per year. The unique constraint on (company_id, year)
    prevents duplicate entries from the ingestion pipeline.

    All financial columns use Numeric for precision — cast to float when building
    Pydantic schemas (Numeric fields serialize as Decimal by default).

    Attributes:
        id: Auto-incremented primary key.
        company_id: Foreign key to companies.id.
        year: Fiscal year (e.g. 2024).
        roe: Return on equity as a percentage (e.g. 28.5 for 28.5%).
        lucro_liquido: Net profit in BRL.
        margem_liquida: Net margin as percentage.
        receita_liquida: Net revenue in BRL.
        divida_liquida: Net debt in BRL.
        ebitda: EBITDA in BRL.
        divida_ebitda: Net debt / EBITDA ratio.
        market_cap: Market capitalization in BRL.
        p_l: Price-to-earnings ratio.
        cagr_lucro: 5-year profit CAGR as percentage.
        company: Back-reference to Company.
    """

    __tablename__ = "financials"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    company_id: int = Column(
        Integer, ForeignKey("companies.id"), nullable=False
    )
    year: int = Column(Integer, nullable=False)

    roe = Column(Numeric(10, 4), nullable=True)
    lucro_liquido = Column(Numeric(20, 2), nullable=True)
    margem_liquida = Column(Numeric(10, 4), nullable=True)
    receita_liquida = Column(Numeric(20, 2), nullable=True)
    divida_liquida = Column(Numeric(20, 2), nullable=True)
    ebitda = Column(Numeric(20, 2), nullable=True)
    divida_ebitda = Column(Numeric(10, 4), nullable=True)
    market_cap = Column(Numeric(20, 2), nullable=True)
    p_l = Column(Numeric(10, 4), nullable=True)
    cagr_lucro = Column(Numeric(10, 4), nullable=True)

    company = relationship("Company", back_populates="financials")

    __table_args__ = (UniqueConstraint("company_id", "year", name="uq_financials_company_year"),)

    def __repr__(self) -> str:
        return f"<Financial company_id={self.company_id} year={self.year}>"
