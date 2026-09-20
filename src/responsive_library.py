"""Load responsive reading Korean/English text from local bible JSON files."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app_paths import get_responsive_en_path, get_responsive_ko_path

RESPONSIVE_NUMBER_PATTERN = re.compile(r"(\d+)")


def parse_responsive_number(value: str) -> int | None:
    """Extract reading number from strings like '137번' or '137'."""
    match = RESPONSIVE_NUMBER_PATTERN.search(str(value).strip())
    if not match:
        return None
    number = int(match.group(1))
    if number < 1 or number > 137:
        return None
    return number


def _ordered_lines(reading: dict[str, Any] | None) -> list[str]:
    if not isinstance(reading, dict):
        return []
    lines: list[str] = []
    for key in sorted(reading.keys(), key=lambda item: int(item) if str(item).isdigit() else 0):
        text = str(reading.get(key, "")).strip()
        if text:
            lines.append(text)
    return lines


@lru_cache(maxsize=1)
def _load_json_payload(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_responsive_ko_lines(number: int) -> list[str]:
    """Return Korean lines for a reading from bible/responsive_ko.json."""
    ko_path = get_responsive_ko_path()
    if ko_path is None:
        return []
    payload = _load_json_payload(str(ko_path))
    return _ordered_lines(payload.get(str(number)))


def load_responsive_en_lines(number: int) -> list[str]:
    """Return English lines for a reading from bible/responsive_en.json."""
    en_path = get_responsive_en_path()
    if en_path is None:
        return []
    payload = _load_json_payload(str(en_path))
    return _ordered_lines(payload.get(str(number)))


def load_responsive_text(number: int, root: Path | None = None) -> str | None:
    """Return Korean bulk text for a numbered responsive reading, or None."""
    del root
    lines = load_responsive_ko_lines(number)
    if not lines:
        return None
    return "\n".join(lines)


def enrich_responsive_data(data: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    """Fill responsive_ko_text / responsive_en_lines from local JSON when unset."""
    updated = dict(data)
    number = parse_responsive_number(str(updated.get("responsive", "")))

    if not str(updated.get("responsive_ko_text", "")).strip() and number is not None:
        text = load_responsive_text(number, root)
        if text:
            updated["responsive_ko_text"] = text

    if number is not None and not updated.get("responsive_en_lines"):
        en_lines = load_responsive_en_lines(number)
        if en_lines:
            updated["responsive_en_lines"] = en_lines

    return updated
