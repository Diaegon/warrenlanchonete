"""Export validation output into backend-compatible files."""

from __future__ import annotations

import csv
import json
from pathlib import Path


BACKEND_COMPANY_FIELDS = ("ticker", "name", "sector", "segment", "asset_type")


def export_backend_rows_csv(report_path: Path, output_path: Path) -> int:
    """Write backend-compatible company rows from a dry-run JSON report."""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = report.get("backend_rows", [])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=BACKEND_COMPANY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in BACKEND_COMPANY_FIELDS})

    return len(rows)
