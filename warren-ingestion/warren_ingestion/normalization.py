"""Normalization helpers for company and ticker matching."""

from __future__ import annotations

import re
import unicodedata


_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")
_CNPJ_RE = re.compile(r"\d")


def normalize_cnpj(value: str | None) -> str:
    """Return CNPJ as digits only."""
    if not value:
        return ""
    return "".join(_CNPJ_RE.findall(value))


def is_valid_cnpj(value: str | None) -> bool:
    """Return True when value looks like a complete CNPJ."""
    return len(normalize_cnpj(value)) == 14


def normalize_ticker(value: str | None) -> str:
    """Normalize a B3 ticker symbol for storage and comparison."""
    if not value:
        return ""
    return value.strip().upper()


def normalize_name(value: str | None) -> str:
    """Normalize names for conservative exact fallback matching."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.upper()
    return _NON_ALNUM_RE.sub(" ", text).strip()
