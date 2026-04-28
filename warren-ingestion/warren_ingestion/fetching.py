"""Small cached HTTP fetcher for official ingestion sources."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_USER_AGENT = "warren-ingestion/0.1 (+https://github.com/warrenlanchonete)"
CVM_CIA_ABERTA_URL = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
)


@dataclass(frozen=True)
class FetchResult:
    url: str
    output_path: str
    metadata_path: str
    from_cache: bool
    fetched_at: str | None
    status_code: int | None
    content_type: str | None
    last_modified: str | None
    bytes_written: int


def fetch_with_cache(
    url: str,
    output_path: Path,
    *,
    max_age_seconds: int,
    retries: int = 3,
    backoff_seconds: float = 1.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> FetchResult:
    """Fetch URL into output_path unless a fresh cached file already exists."""
    metadata_path = output_path.with_suffix(output_path.suffix + ".metadata.json")
    if _is_fresh(output_path, max_age_seconds):
        metadata = _read_metadata(metadata_path)
        return FetchResult(
            url=url,
            output_path=str(output_path),
            metadata_path=str(metadata_path),
            from_cache=True,
            fetched_at=metadata.get("fetched_at"),
            status_code=metadata.get("status_code"),
            content_type=metadata.get("content_type"),
            last_modified=metadata.get("last_modified"),
            bytes_written=output_path.stat().st_size,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            request = Request(url, headers={"User-Agent": user_agent})
            with urlopen(request, timeout=30) as response:
                body = response.read()
                output_path.write_bytes(body)
                result = FetchResult(
                    url=url,
                    output_path=str(output_path),
                    metadata_path=str(metadata_path),
                    from_cache=False,
                    fetched_at=datetime.now(UTC).isoformat(),
                    status_code=getattr(response, "status", None),
                    content_type=response.headers.get("Content-Type"),
                    last_modified=response.headers.get("Last-Modified"),
                    bytes_written=len(body),
                )
                metadata_path.write_text(
                    json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                return result
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(backoff_seconds * (2 ** (attempt - 1)))

    raise RuntimeError(f"failed to fetch {url}: {last_error}") from last_error


def _is_fresh(path: Path, max_age_seconds: int) -> bool:
    if max_age_seconds <= 0 or not path.exists():
        return False
    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds <= max_age_seconds


def _read_metadata(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
