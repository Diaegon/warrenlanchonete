from warren_ingestion.models import B3TickerRow, CvmCompany, KnownCompany
from warren_ingestion.validation import validate_tickers


def test_validate_tickers_matches_by_cnpj_and_outputs_backend_rows() -> None:
    report = validate_tickers(
        known_companies=[KnownCompany(name="Petróleo Brasileiro S.A.", cnpj="33000167000101")],
        b3_rows=[
            B3TickerRow(
                ticker="PETR4",
                name="Petrobras",
                cnpj="33000167000101",
                sector="Petróleo, Gás e Biocombustíveis",
                segment="Exploração e/ou Refino",
            )
        ],
    )

    assert report.matched_by_cnpj == 1
    assert report.matched_by_name == 0
    assert report.unmatched_b3_rows == []
    assert report.backend_rows[0].ticker == "PETR4"
    assert report.backend_rows[0].asset_type == "STOCK"


def test_validate_tickers_uses_name_fallback_when_cnpj_is_missing() -> None:
    report = validate_tickers(
        known_companies=[KnownCompany(name="WEG S.A.", cnpj="84429695000111")],
        b3_rows=[B3TickerRow(ticker="WEGE3", name="WEG S A", cnpj="")],
    )

    assert report.matched_by_cnpj == 0
    assert report.matched_by_name == 1
    assert report.missing_cnpj_rows[0]["ticker"] == "WEGE3"
    assert report.known_companies_without_ticker == []


def test_validate_tickers_reports_unmatched_and_inactive_cvm_status() -> None:
    report = validate_tickers(
        known_companies=[
            KnownCompany(name="Valid Company", cnpj="11111111000111"),
            KnownCompany(name="Missing Company", cnpj="22222222000122"),
        ],
        b3_rows=[
            B3TickerRow(ticker="BAD", name="Invalid Ticker Company", cnpj="11111111000111"),
            B3TickerRow(ticker="ABCD3", name="Unknown Company", cnpj="33333333000133"),
        ],
        cvm_companies=[
            CvmCompany(name="Valid Company", cnpj="11111111000111", status="Cancelado")
        ],
    )

    assert report.matched_by_cnpj == 1
    assert report.invalid_tickers[0]["ticker"] == "BAD"
    assert report.unmatched_b3_rows[0]["ticker"] == "ABCD3"
    assert report.cvm_status_warnings[0]["cvm_status"] == "Cancelado"
    assert report.known_companies_without_ticker == [
        {"cnpj": "22222222000122", "name": "Missing Company"}
    ]
