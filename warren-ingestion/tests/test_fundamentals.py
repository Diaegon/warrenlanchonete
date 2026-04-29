"""Tests for CVM DFP fundamentals builder."""

from __future__ import annotations

import csv
import zipfile

from warren_ingestion.fundamentals import build_fundamentals_csv, dfp_zip_url


def _write_zip(path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content.encode("latin-1"))


def _dre(*, cnpj: str, receita: str, lucro: str) -> str:
    return "\n".join(
        [
            "CNPJ_CIA;CD_CONTA;DS_CONTA;VL_CONTA;ESCALA_MOEDA;ORDEM_EXERC",
            f"{cnpj};3.01;Receita de Venda de Bens e/ou Serviços;{receita};MIL;ÚLTIMO",
            f"{cnpj};3.11;Lucro/Prejuízo Consolidado do Período;{lucro};MIL;ÚLTIMO",
            f"{cnpj};3.11;Lucro/Prejuízo Consolidado do Período;1;MIL;PENÚLTIMO",
        ]
    )


def _bpa(*, cnpj: str, caixa: str) -> str:
    return "\n".join(
        [
            "CNPJ_CIA;CD_CONTA;DS_CONTA;VL_CONTA;ESCALA_MOEDA;ORDEM_EXERC",
            f"{cnpj};1.01.01;Caixa e Equivalentes de Caixa;{caixa};MIL;ÚLTIMO",
        ]
    )


def _bpp(*, cnpj: str, patrimonio: str, divida_curta: str, divida_longa: str) -> str:
    return "\n".join(
        [
            "CNPJ_CIA;CD_CONTA;DS_CONTA;VL_CONTA;ESCALA_MOEDA;ORDEM_EXERC",
            f"{cnpj};2.03;Patrimônio Líquido Consolidado;{patrimonio};MIL;ÚLTIMO",
            f"{cnpj};2.01.04;Empréstimos e Financiamentos;{divida_curta};MIL;ÚLTIMO",
            f"{cnpj};2.02.01;Empréstimos e Financiamentos;{divida_longa};MIL;ÚLTIMO",
        ]
    )


def test_dfp_zip_url_uses_official_cvm_path() -> None:
    assert (
        dfp_zip_url(2024)
        == "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2024.zip"
    )


def test_build_fundamentals_csv_extracts_annual_metrics(tmp_path) -> None:
    b3_path = tmp_path / "tickers.csv"
    b3_path.write_text(
        "\n".join(
            [
                "ticker,name,cnpj,sector,segment,asset_type,source_url,source_updated_at",
                "WEGE3,WEG S.A.,84429695000111,Bens Industriais,Máquinas,STOCK,,",
            ]
        ),
        encoding="utf-8",
    )
    zip_path = tmp_path / "dfp_cia_aberta_2024.zip"
    _write_zip(
        zip_path,
        {
            "dfp_cia_aberta_DRE_con_2024.csv": _dre(
                cnpj="84.429.695/0001-11",
                receita="38090000",
                lucro="5789000",
            ),
            "dfp_cia_aberta_BPA_con_2024.csv": _bpa(
                cnpj="84.429.695/0001-11",
                caixa="1000000",
            ),
            "dfp_cia_aberta_BPP_con_2024.csv": _bpp(
                cnpj="84.429.695/0001-11",
                patrimonio="20312000",
                divida_curta="400000",
                divida_longa="1100000",
            ),
        },
    )
    output_path = tmp_path / "fundamentals.csv"

    result = build_fundamentals_csv(
        b3_tickers_path=b3_path,
        dfp_zip_paths=[zip_path],
        output_path=output_path,
    )

    rows = list(csv.DictReader(output_path.open(encoding="utf-8")))
    assert result.rows_written == 1
    assert result.companies_matched == 1
    assert rows == [
        {
            "ticker": "WEGE3",
            "year": "2024",
            "roe": "28.5004",
            "lucro_liquido": "5.789E+9",
            "margem_liquida": "15.1982",
            "receita_liquida": "3.809E+10",
            "divida_liquida": "5E+8",
            "ebitda": "",
            "divida_ebitda": "",
            "market_cap": "",
            "p_l": "",
            "cagr_lucro": "",
        }
    ]


def test_build_fundamentals_csv_calculates_profit_cagr_when_prior_year_exists(tmp_path) -> None:
    b3_path = tmp_path / "tickers.csv"
    b3_path.write_text(
        "\n".join(
            [
                "ticker,name,cnpj,sector,segment,asset_type,source_url,source_updated_at",
                "TEST3,TEST S.A.,11111111000111,Bens Industriais,Máquinas,STOCK,,",
            ]
        ),
        encoding="utf-8",
    )
    zip_2019 = tmp_path / "dfp_cia_aberta_2019.zip"
    zip_2024 = tmp_path / "dfp_cia_aberta_2024.zip"
    _write_zip(
        zip_2019,
        {
            "dfp_cia_aberta_DRE_con_2019.csv": _dre(
                cnpj="11.111.111/0001-11",
                receita="1000000",
                lucro="100000",
            ),
        },
    )
    _write_zip(
        zip_2024,
        {
            "dfp_cia_aberta_DRE_con_2024.csv": _dre(
                cnpj="11.111.111/0001-11",
                receita="2000000",
                lucro="200000",
            ),
        },
    )

    output_path = tmp_path / "fundamentals.csv"
    build_fundamentals_csv(
        b3_tickers_path=b3_path,
        dfp_zip_paths=[zip_2019, zip_2024],
        output_path=output_path,
    )

    rows = list(csv.DictReader(output_path.open(encoding="utf-8")))
    row_2024 = next(row for row in rows if row["year"] == "2024")
    assert row_2024["cagr_lucro"] == "14.8698"


def test_build_fundamentals_csv_ignores_unmatched_cnpj_and_fiis(tmp_path) -> None:
    b3_path = tmp_path / "tickers.csv"
    b3_path.write_text(
        "\n".join(
            [
                "ticker,name,cnpj,sector,segment,asset_type,source_url,source_updated_at",
                "MXRF11,MAXI RENDA,12345678000199,FII,Recebíveis,FII,,",
            ]
        ),
        encoding="utf-8",
    )
    zip_path = tmp_path / "dfp_cia_aberta_2024.zip"
    _write_zip(
        zip_path,
        {
            "dfp_cia_aberta_DRE_con_2024.csv": _dre(
                cnpj="12.345.678/0001-99",
                receita="1000000",
                lucro="100000",
            ),
        },
    )

    output_path = tmp_path / "fundamentals.csv"
    result = build_fundamentals_csv(
        b3_tickers_path=b3_path,
        dfp_zip_paths=[zip_path],
        output_path=output_path,
    )

    rows = list(csv.DictReader(output_path.open(encoding="utf-8")))
    assert result.rows_written == 0
    assert rows == []
