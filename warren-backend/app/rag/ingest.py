"""CLI ingestion script: PDF/HTML → chunks → embeddings → ChromaDB.

Entry point: python -m app.rag.ingest

Scans the source directory (default: buffett_letters/, fallback: rag_data/pdfs/)
for files matching YYYY.pdf, YYYY_letter.pdf, YYYY.html, or YYYY_letter.html.

Extracts text via PyMuPDF (PDF) or html.parser (HTML), splits into chunks,
and stores in the 'buffett_letters' ChromaDB collection.

Idempotent: if any document with source_file = 'YYYY.pdf' already exists in the
collection, the entire file is skipped (S11 optimization).

Usage:
    uv run python -m app.rag.ingest
    uv run python -m app.rag.ingest --source-dir path/to/letters
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import fitz  # PyMuPDF
import structlog
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from app.config import settings
from app.rag.client import get_collection

logger = structlog.get_logger(__name__)

# Accepts: YYYY.pdf, YYYY_letter.pdf, YYYY.html, YYYY_letter.html
_FILENAME_PATTERN = re.compile(r"^(\d{4})(?:_letter)?\.(pdf|html)$")

_LONG_PARAGRAPH_THRESHOLD = 400
_CHUNK_SIZE = 1200
_CHUNK_OVERLAP = 150
_MIN_CHUNK_LENGTH = 100


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts: list[str] = []

    def handle_data(self, data: str) -> None:
        t = data.strip()
        if t:
            self.texts.append(t)


def parse_year_from_filename(filename: str) -> int | None:
    """Extract year from filenames matching YYYY.pdf, YYYY_letter.pdf, YYYY.html, YYYY_letter.html.

    Returns:
        int year if the filename matches, None otherwise.
    """
    match = _FILENAME_PATTERN.match(filename)
    if match:
        return int(match.group(1))
    return None


def _extract_text_from_file(path: str) -> str:
    """Extract plain text from a PDF or HTML file.

    For PDF: uses PyMuPDF (fitz). For HTML: uses stdlib html.parser.
    Returns empty string if the file cannot be read as text.
    """
    lower = path.lower()
    if lower.endswith(".pdf"):
        parts: list[str] = []
        with fitz.open(path) as doc:
            for page in doc:
                parts.append(page.get_text())
        return "\n\n".join(parts)

    # HTML path: check raw bytes first to reject binary files
    try:
        with open(path, "rb") as f:
            raw = f.read(1024)
        # Count control bytes (< 0x20 excluding \t \n \r, and > 0x7e)
        non_text = sum(
            1 for b in raw if (b < 0x20 and b not in (0x09, 0x0A, 0x0D)) or b > 0x7E
        )
        if non_text / max(len(raw), 1) > 0.15:
            return ""
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        parser = _TextExtractor()
        parser.feed(content)
        return " ".join(parser.texts)
    except Exception:
        return ""


def ingest_pdf(
    source_file: str,
    year: int,
    collection,
    embedding_fn,
    pdf_path: str | None = None,
) -> int:
    """Ingest a single PDF or HTML file into the ChromaDB collection.

    Args:
        source_file: Filename (e.g. '2004.pdf') — stored as metadata.
        year: Integer year parsed from the filename.
        collection: ChromaDB collection to store chunks in.
        embedding_fn: LangChain embedding function (OpenAIEmbeddings).
        pdf_path: Explicit path to the file. If None, resolved from source directory.

    Returns:
        Number of chunks ingested (0 if skipped as duplicate or unreadable).
    """
    log = logger.bind(source_file=source_file, year=year)

    # Idempotency check (S11): skip if any chunk for this file already exists
    existing = collection.get(where={"source_file": source_file}, limit=1)
    if existing["ids"]:
        log.info("ingest.file.skipped", reason="already_ingested")
        return 0

    log.info("ingest.file.started")

    if pdf_path is None:
        source_dir = _resolve_source_dir()
        pdf_path = str(source_dir / source_file)

    full_text = _extract_text_from_file(pdf_path)
    if not full_text.strip():
        log.warning("ingest.file.skipped", reason="unreadable_content")
        return 0

    paragraphs = full_text.split("\n\n")
    splitter = RecursiveCharacterTextSplitter(chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP)

    chunks: list[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) > _LONG_PARAGRAPH_THRESHOLD:
            chunks.extend(splitter.split_text(para))
        else:
            chunks.append(para)

    chunks = [c for c in chunks if len(c) >= _MIN_CHUNK_LENGTH]

    if not chunks:
        log.warning("ingest.file.no_chunks")
        return 0

    source_stem = Path(source_file).stem
    ids = [f"{source_stem}_chunk_{i:03d}" for i in range(len(chunks))]
    metadatas = [
        {"year": year, "letter_type": "shareholder_letter", "topic": "", "source_file": source_file}
        for _ in chunks
    ]

    embeddings = embedding_fn.embed_documents(chunks)
    collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)

    log.info("ingest.file.completed", chunks_ingested=len(chunks))
    return len(chunks)


def _resolve_source_dir() -> Path:
    """Return the directory to scan, preferring buffett_letters/ over rag_data/pdfs/."""
    for candidate in [Path("buffett_letters"), Path("rag_data/pdfs")]:
        if candidate.exists():
            return candidate
    return Path("buffett_letters")


def run(source_dir: Path | None = None) -> None:
    """Main entry point: scan source directory and ingest matching files.

    Args:
        source_dir: Directory to scan. Defaults to buffett_letters/ (falls back to rag_data/pdfs/).
    """
    if source_dir is None:
        source_dir = _resolve_source_dir()

    collection = get_collection()
    embedding_fn = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )

    all_files = sorted(source_dir.glob("*.pdf")) + sorted(source_dir.glob("*.html"))
    logger.info("ingest.scan.started", file_count=len(all_files), directory=str(source_dir))

    total_ingested = 0
    total_skipped = 0

    for file_path in all_files:
        filename = file_path.name
        year = parse_year_from_filename(filename)

        if year is None:
            logger.warning(
                "ingest.file.skipped",
                filename=filename,
                reason="filename_does_not_match_pattern",
            )
            total_skipped += 1
            continue

        count = ingest_pdf(filename, year, collection, embedding_fn, pdf_path=str(file_path))
        total_ingested += count

    logger.info(
        "ingest.scan.completed",
        total_chunks_ingested=total_ingested,
        files_skipped=total_skipped,
    )


if __name__ == "__main__":
    source_dir = None
    if "--source-dir" in sys.argv:
        idx = sys.argv.index("--source-dir")
        if idx + 1 < len(sys.argv):
            source_dir = Path(sys.argv[idx + 1])
    run(source_dir=source_dir)
