import json
from pathlib import Path

from warren_ingestion.exporters import export_backend_rows_csv


def test_export_backend_rows_csv_writes_backend_shape(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    output = tmp_path / "backend_companies.csv"
    report.write_text(
        json.dumps(
            {
                "backend_rows": [
                    {
                        "ticker": "WEGE3",
                        "name": "WEG S.A.",
                        "sector": "Bens Industriais",
                        "segment": "Máquinas e Equipamentos",
                        "asset_type": "STOCK",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rows_written = export_backend_rows_csv(report, output)

    assert rows_written == 1
    assert output.read_text(encoding="utf-8").splitlines() == [
        "ticker,name,sector,segment,asset_type",
        "WEGE3,WEG S.A.,Bens Industriais,Máquinas e Equipamentos,STOCK",
    ]
