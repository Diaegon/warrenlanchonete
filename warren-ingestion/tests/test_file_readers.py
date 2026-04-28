from pathlib import Path

from warren_ingestion.file_readers import read_b3_tickers, read_known_companies


def test_read_known_companies_supports_semicolon_csv(tmp_path: Path) -> None:
    path = tmp_path / "known.csv"
    path.write_text(
        "nome;cnpj\nWEG S.A.;84.429.695/0001-11\n",
        encoding="utf-8",
    )

    companies = read_known_companies(path)

    assert companies[0].name == "WEG S.A."
    assert companies[0].cnpj == "84429695000111"


def test_read_known_companies_supports_latin_1_csv(tmp_path: Path) -> None:
    path = tmp_path / "known_latin1.csv"
    path.write_bytes("nome;cnpj\nAÇÚCAR S.A.;12.345.678/0001-90\n".encode("latin-1"))

    companies = read_known_companies(path)

    assert companies[0].name == "AÇÚCAR S.A."
    assert companies[0].cnpj == "12345678000190"


def test_read_known_companies_falls_back_when_sniffer_fails(tmp_path: Path) -> None:
    path = tmp_path / "known_one_column_style.csv"
    path.write_text(
        "nome;cnpj\nOnly One;12.345.678/0001-90\n",
        encoding="utf-8",
    )

    companies = read_known_companies(path)

    assert companies[0].name == "Only One"


def test_read_b3_tickers_supports_common_field_aliases(tmp_path: Path) -> None:
    path = tmp_path / "b3.csv"
    path.write_text(
        "codigo_negociacao,nome,cnpj,setor,segmento\n"
        "PETR4,Petrobras,33.000.167/0001-01,Energia,Petroleo\n",
        encoding="utf-8",
    )

    rows = read_b3_tickers(path)

    assert rows[0].ticker == "PETR4"
    assert rows[0].name == "Petrobras"
    assert rows[0].cnpj == "33000167000101"
    assert rows[0].sector == "Energia"


def test_read_b3_tickers_supports_json_results_payload(tmp_path: Path) -> None:
    path = tmp_path / "b3.json"
    path.write_text(
        """
        {
          "results": [
            {
              "securityCode": "WEGE3",
              "companyName": "WEG S.A.",
              "cnpj": "84429695000111",
              "segment": "Máquinas e Equipamentos"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    rows = read_b3_tickers(path)

    assert rows[0].ticker == "WEGE3"
    assert rows[0].name == "WEG S.A."
    assert rows[0].cnpj == "84429695000111"
    assert rows[0].segment == "Máquinas e Equipamentos"
