from warren_ingestion.b3 import _detail_to_ticker_rows, _split_industry_classification


def test_detail_to_ticker_rows_expands_equity_other_codes() -> None:
    rows = _detail_to_ticker_rows(
        {
            "companyName": "PETROLEO BRASILEIRO S.A. PETROBRAS",
            "cnpj": "33000167000101",
            "industryClassification": (
                "Petróleo. Gás e Biocombustíveis / "
                "Petróleo. Gás e Biocombustíveis / "
                "Exploração. Refino e Distribuição"
            ),
            "code": "PETR4",
            "lastDate": "24/04/2026 23:38:45",
            "otherCodes": [
                {"code": "PETR3", "isin": "BRPETRACNOR9"},
                {"code": "PETR4", "isin": "BRPETRACNPR6"},
                {"code": "PETR-DEB62", "isin": "BRPETRDBS092"},
            ],
        }
    )

    assert [row.ticker for row in rows] == ["PETR3", "PETR4"]
    assert rows[0].name == "PETROLEO BRASILEIRO S.A. PETROBRAS"
    assert rows[0].cnpj == "33000167000101"
    assert rows[0].sector == "Petróleo. Gás e Biocombustíveis"
    assert rows[0].segment == "Exploração. Refino e Distribuição"


def test_split_industry_classification_handles_empty_value() -> None:
    assert _split_industry_classification("") == (None, None)
