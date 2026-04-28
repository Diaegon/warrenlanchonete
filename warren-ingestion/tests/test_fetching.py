import json
import os
import time
from pathlib import Path

from warren_ingestion.fetching import fetch_with_cache


def test_fetch_with_cache_reuses_fresh_file(tmp_path: Path) -> None:
    output = tmp_path / "source.csv"
    metadata = tmp_path / "source.csv.metadata.json"
    output.write_text("cached\n", encoding="utf-8")
    metadata.write_text(
        json.dumps(
            {
                "fetched_at": "2026-04-28T00:00:00+00:00",
                "status_code": 200,
                "content_type": "text/csv",
                "last_modified": "Tue, 28 Apr 2026 00:00:00 GMT",
            }
        ),
        encoding="utf-8",
    )

    result = fetch_with_cache(
        "https://example.invalid/source.csv",
        output,
        max_age_seconds=3600,
    )

    assert result.from_cache is True
    assert result.bytes_written == len("cached\n")
    assert result.status_code == 200


def test_fetch_with_cache_fetches_file_url_when_cache_is_stale(tmp_path: Path) -> None:
    source = tmp_path / "remote.csv"
    output = tmp_path / "cache" / "source.csv"
    source.write_text("fresh\n", encoding="utf-8")
    output.parent.mkdir()
    output.write_text("stale\n", encoding="utf-8")
    old_time = time.time() - 7200
    os.utime(output, (old_time, old_time))

    result = fetch_with_cache(
        source.as_uri(),
        output,
        max_age_seconds=1,
    )

    assert result.from_cache is False
    assert output.read_text(encoding="utf-8") == "fresh\n"
    assert Path(result.metadata_path).exists()
