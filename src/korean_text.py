"""Format Korean sermon text extracted from PDFs."""

from __future__ import annotations

import re
from typing import Any

HANGUL_PATTERN = re.compile(r"[\uAC00-\uD7A3]")

# (8절), (10-11절)
VERSE_KO_PATTERN = re.compile(r"\s*\(\s*\d+(?:\s*-\s*\d+)?\s*절\s*\)")

# (verse 8), (verses 10-11), (Verse 8)
VERSE_EN_PATTERN = re.compile(
    r"\s*\(\s*(?:verse[s]?\s+)?\d+(?:\s*[-–]\s*\d+)?\s*\)",
    re.IGNORECASE,
)

PART_INDEX_PREFIX = re.compile(r"^\d+\.\s*")

SERMON_PART_FIELDS = (
    "sermon_part1",
    "sermon_part1_desc",
    "sermon_part2",
    "sermon_part2_desc",
    "sermon_part3",
    "sermon_part3_desc",
)

_kiwi = None
_kiwi_failed = False


def contains_korean(text: str) -> bool:
    return bool(HANGUL_PATTERN.search(text))


def _get_kiwi():
    global _kiwi, _kiwi_failed
    if _kiwi_failed:
        return None
    if _kiwi is not None:
        return _kiwi

    try:
        from kiwipiepy import Kiwi

        _kiwi = Kiwi()
    except Exception:
        _kiwi_failed = True
        _kiwi = None
    return _kiwi


def space_korean_text(text: str) -> str:
    """Insert spaces between Korean words when PDF text is concatenated."""
    cleaned = text.strip()
    if not cleaned or not contains_korean(cleaned):
        return cleaned

    kiwi = _get_kiwi()
    if kiwi is None:
        return cleaned

    try:
        return kiwi.space(cleaned)
    except Exception:
        return cleaned


def strip_korean_verse_reference(text: str) -> str:
    return VERSE_KO_PATTERN.sub("", text).strip()


def strip_english_verse_reference(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        stripped = VERSE_EN_PATTERN.sub("", line).strip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)


def format_sermon_part_title(text: str) -> str:
    """Remove numbering, verse markers, and fix Korean spacing."""
    cleaned = PART_INDEX_PREFIX.sub("", text.strip())
    cleaned = strip_korean_verse_reference(cleaned)
    return space_korean_text(cleaned)


def format_sermon_part_desc(text: str) -> str:
    """Fix Korean spacing for sermon part descriptions."""
    cleaned = space_korean_text(text.strip())
    return re.sub(r"\s*=\s*", " = ", cleaned)


def normalize_week_sermon_text(data: dict[str, Any]) -> dict[str, Any]:
    """Apply sermon part formatting to weekly data."""
    normalized = dict(data)

    for index in (1, 2, 3):
        part_key = f"sermon_part{index}"
        desc_key = f"sermon_part{index}_desc"
        if normalized.get(part_key):
            normalized[part_key] = format_sermon_part_title(str(normalized[part_key]))
        if normalized.get(desc_key):
            normalized[desc_key] = format_sermon_part_desc(str(normalized[desc_key]))

    if normalized.get("sermon_title2"):
        normalized["sermon_title2"] = space_korean_text(str(normalized["sermon_title2"]))

    return normalized
