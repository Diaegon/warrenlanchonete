"""SQLAlchemy ORM model for the companies table."""
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class Company(Base):
    """ORM model representing a Brazilian company or FII tracked by Warren Lanchonete.

    Attributes:
        id: Auto-incremented primary key.
        ticker: B3 ticker symbol (e.g. 'WEGE3', 'PETR4'). Unique, indexed.
        name: Full company name (e.g. 'WEG S.A.').
        sector: B3 sector classification (e.g. 'Industrial', 'Energia').
        segment: B3 segment within the sector (e.g. 'Máquinas e Equipamentos').
        asset_type: 'STOCK' or 'FII'.
        financials: List of Financial records ordered by year descending.
    """

    __tablename__ = "companies"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    ticker: str = Column(String(10), unique=True, nullable=False, index=True)
    name: str = Column(String(200), nullable=False)
    sector: str | None = Column(String(100), nullable=True)
    segment: str | None = Column(String(100), nullable=True)
    asset_type: str = Column(String(10), nullable=False)  # 'STOCK' or 'FII'

    financials = relationship(
        "Financial",
        back_populates="company",
        order_by="Financial.year.desc()",
    )

    def __repr__(self) -> str:
        return f"<Company ticker={self.ticker!r} name={self.name!r}>"
