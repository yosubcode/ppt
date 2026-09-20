"""Rebuild bible/responsive_reading/responsive_en.json from responsive_ko.json.

Korean source of truth is bible/responsive_reading/responsive_ko.json.
English is translated once and stored locally so PPT generation does not re-translate.

Format:
  { "<reading>": { "<line>": "<text>" } }
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from app_paths import load_app_env
from translator import (
    _parse_numbered_translation_block,
    _translate_with_google,
    translate_responsive_lines_esv,
)

KO_PATH = ROOT / "bible" / "responsive_reading" / "responsive_ko.json"
EN_PATH = ROOT / "bible" / "responsive_reading" / "responsive_en.json"
LOG_PATH = ROOT / "bible" / "responsive_reading" / "responsive_translate_log.txt"

READING_GAP_SECONDS = 0.4


def _translate_reading_lines(ko_lines: list[str]) -> list[str]:
    """Translate one reading. Prefer one numbered Google call; fall back to line API."""
    if not ko_lines:
        return []

    numbered = "\n".join(f"{index}. {line}" for index, line in enumerate(ko_lines, start=1))
    try:
        if len(numbered) <= 4500:
            block = _translate_with_google(numbered)
            parsed = _parse_numbered_translation_block(block, len(ko_lines))
            if len(parsed) == len(ko_lines) and all(line.strip() for line in parsed):
                return parsed
    except Exception:
        pass

    return translate_responsive_lines_esv(ko_lines)


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _log(message: str) -> None:
    print(message, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def _ordered_lines(reading: dict) -> list[str]:
    lines: list[str] = []
    for key in sorted(reading.keys(), key=lambda item: int(item) if str(item).isdigit() else 0):
        text = str(reading.get(key, "")).strip()
        if text:
            lines.append(text)
    return lines


def build_en_payload(ko_payload: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    existing = _load_json(EN_PATH)
    en_payload: dict[str, dict[str, str]] = {
        key: dict(value) for key, value in existing.items() if isinstance(value, dict)
    }

    for number in range(1, 138):
        key = str(number)
        ko_reading = ko_payload.get(key)
        if not isinstance(ko_reading, dict):
            raise SystemExit(f"Missing Korean reading in JSON: {key}")

        ko_lines = _ordered_lines(ko_reading)
        expected = len(ko_lines)
        current = en_payload.get(key, {})
        if (
            isinstance(current, dict)
            and len(current) == expected
            and all(str(current.get(str(i), "")).strip() for i in range(1, expected + 1))
        ):
            _log(f"skip {key}: already translated ({expected} lines)")
            continue

        _log(f"translate {key}: {expected} lines")
        try:
            en_lines = _translate_reading_lines(ko_lines)
            if len(en_lines) != expected or any(not line.strip() for line in en_lines):
                raise RuntimeError(
                    f"incomplete translation for {key}: got {len(en_lines)} lines"
                )
            en_payload[key] = {
                str(index): line.strip()
                for index, line in enumerate(en_lines, start=1)
            }
            _save_json(EN_PATH, en_payload)
            _log(f"saved {key}")
        except Exception as error:
            _log(f"FAIL {key}: {error}")
            _log(traceback.format_exc())
            _save_json(EN_PATH, en_payload)
            raise

        time.sleep(READING_GAP_SECONDS)

    return en_payload


def main() -> int:
    load_app_env()
    LOG_PATH.write_text("", encoding="utf-8")

    if not KO_PATH.is_file():
        raise SystemExit(f"Missing Korean source JSON: {KO_PATH}")

    ko_payload = _load_json(KO_PATH)
    if not isinstance(ko_payload, dict) or not ko_payload:
        raise SystemExit(f"Invalid Korean source JSON: {KO_PATH}")

    en_payload = build_en_payload(ko_payload)
    _save_json(EN_PATH, en_payload)
    en_lines = sum(len(v) for v in en_payload.values() if isinstance(v, dict))
    _log(f"Wrote {EN_PATH} ({len(en_payload)} readings, {en_lines} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
