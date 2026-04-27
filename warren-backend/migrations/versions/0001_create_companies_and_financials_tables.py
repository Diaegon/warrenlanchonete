"""create companies and financials tables

Revision ID: 0001
Revises:
Create Date: 2026-04-27 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create companies and financials tables with all indexes."""
    # companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("segment", sa.String(length=100), nullable=True),
        sa.Column("asset_type", sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker"),
    )
    op.create_index(op.f("ix_companies_ticker"), "companies", ["ticker"], unique=True)
    op.create_index("ix_companies_asset_type", "companies", ["asset_type"], unique=False)

    # financials table
    op.create_table(
        "financials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("roe", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("lucro_liquido", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("margem_liquida", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("receita_liquida", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("divida_liquida", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("ebitda", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("divida_ebitda", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("market_cap", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("p_l", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("cagr_lucro", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "year", name="uq_financials_company_year"),
    )
    op.create_index(
        "ix_financials_company_year",
        "financials",
        ["company_id", "year"],
        unique=False,
    )


def downgrade() -> None:
    """Drop companies and financials tables."""
    op.drop_index("ix_financials_company_year", table_name="financials")
    op.drop_table("financials")
    op.drop_index("ix_companies_asset_type", table_name="companies")
    op.drop_index(op.f("ix_companies_ticker"), table_name="companies")
    op.drop_table("companies")
