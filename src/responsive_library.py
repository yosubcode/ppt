"""Load responsive reading Korean text from numbered files in responsive_readings/."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app_paths import get_app_root

RESPONSIVE_READINGS_DIR_NAME = "responsive_readings"
RESPONSIVE_NUMBER_PATTERN = re.compile(r"(\d+)")


def get_responsive_readings_dir(root: Path | None = None) -> Path:
    return (root or get_app_root()) / RESPONSIVE_READINGS_DIR_NAME


def parse_responsive_number(value: str) -> int | None:
    """Extract reading number from strings like '137번' or '137'."""
    match = RESPONSIVE_NUMBER_PATTERN.search(str(value).strip())
    if not match:
        return None
    number = int(match.group(1))
    if number < 1 or number > 137:
        return None
    return number


def responsive_text_path(number: int, root: Path | None = None) -> Path:
    return get_responsive_readings_dir(root) / f"{number}.txt"


def load_responsive_text(number: int, root: Path | None = None) -> str | None:
    """Return file contents for a numbered responsive reading, or None if missing/empty."""
    path = responsive_text_path(number, root)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def enrich_responsive_data(data: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    """Fill responsive_ko_text from responsive_readings/{n}.txt when not already set."""
    if str(data.get("responsive_ko_text", "")).strip():
        return data

    number = parse_responsive_number(str(data.get("responsive", "")))
    if number is None:
        return data

    text = load_responsive_text(number, root)
    if text:
        updated = dict(data)
        updated["responsive_ko_text"] = text
        return updated
    return data
