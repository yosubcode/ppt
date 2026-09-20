"""Parse responsive reading bulk text into one line per slide."""

from __future__ import annotations

import re
from typing import Any

from translator import translate_responsive_lines_esv

# (다같이), (1 - 6), (마 3 : 16 - 17), etc.
RESPONSIVE_PARENTHETICAL_PATTERN = re.compile(r"\s*\([^)]*\)")


def strip_responsive_scripture_references(text: str) -> str:
    """Remove parenthetical markers and scripture refs from slide output text."""
    cleaned = RESPONSIVE_PARENTHETICAL_PATTERN.sub("", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def split_responsive_lines(text: str) -> list[str]:
    """Split bulk pasted Korean responsive reading into non-empty lines."""
    return [line.strip() for line in str(text).splitlines() if line.strip()]


def join_responsive_lines(lines: list[dict[str, Any]], field: str) -> str:
    """Rebuild bulk paste text from structured responsive entries."""
    values: list[str] = []
    for item in lines:
        if not isinstance(item, dict):
            continue
        value = str(item.get(field, "")).strip()
        if value:
            values.append(value)
    return "\n".join(values)


def build_responsive_lines(
    data: dict[str, Any],
    *,
    translate: bool = True,
) -> list[dict[str, str]]:
    """Build ordered responsive reading entries with Korean and English text."""
    if isinstance(data.get("responsive_lines"), list) and not data.get("responsive_ko_text"):
        lines: list[dict[str, str]] = []
        for item in data["responsive_lines"]:
            if not isinstance(item, dict):
                continue
            ko = strip_responsive_scripture_references(str(item.get("ko", "")).strip())
            en = str(item.get("en", "")).strip()
            if en:
                en = strip_responsive_scripture_references(en)
            if ko or en:
                lines.append({"ko": ko, "en": en})
        return lines

    ko_lines = split_responsive_lines(str(data.get("responsive_ko_text", "")))
    ko_lines = [strip_responsive_scripture_references(line) for line in ko_lines]
    ko_lines = [line for line in ko_lines if line]
    if not ko_lines:
        return []

    en_lines: list[str] = []
    local_en = [
        strip_responsive_scripture_references(str(item).strip())
        for item in (data.get("responsive_en_lines") or [])
    ]
    local_en = [line for line in local_en if line]

    # Prefer prebuilt local English so PPT generation does not re-translate.
    if len(local_en) == len(ko_lines):
        en_lines = local_en
    elif translate:
        en_lines = translate_responsive_lines_esv(ko_lines)
    elif local_en:
        en_lines = local_en

    result: list[dict[str, str]] = []
    for index, ko in enumerate(ko_lines):
        en = en_lines[index] if index < len(en_lines) else ""
        result.append({"ko": ko, "en": en})
    return result


def responsive_lines_ready_for_insert(
    data: dict[str, Any],
    *,
    translate: bool = True,
) -> list[dict[str, str]]:
    """Return responsive lines that have Korean or English text."""
    return [
        line
        for line in build_responsive_lines(data, translate=translate)
        if line.get("ko") or line.get("en")
    ]
