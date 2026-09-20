"""Thorough audit of bible/gae_verses.json against expected canon and live bskorea."""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bible_books import BOOKS
from bible_fetcher import (
    BSKOREA_URL,
    USER_AGENT,
    VERSE_NUMBER_PATTERN,
    _clean_html_text,
    _parse_verse_number_token,
)

CHAPTER_COUNTS: dict[str, int] = {
    "gen": 50,
    "exo": 40,
    "lev": 27,
    "num": 36,
    "deu": 34,
    "jos": 24,
    "jdg": 21,
    "rut": 4,
    "1sa": 31,
    "2sa": 24,
    "1ki": 22,
    "2ki": 25,
    "1ch": 29,
    "2ch": 36,
    "ezr": 10,
    "neh": 13,
    "est": 10,
    "job": 42,
    "psa": 150,
    "pro": 31,
    "ecc": 12,
    "sng": 8,
    "isa": 66,
    "jer": 52,
    "lam": 5,
    "ezk": 48,
    "dan": 12,
    "hos": 14,
    "jol": 3,
    "amo": 9,
    "oba": 1,
    "jnh": 4,
    "mic": 7,
    "nam": 3,
    "hab": 3,
    "zep": 3,
    "hag": 2,
    "zec": 14,
    "mal": 4,
    "mat": 28,
    "mrk": 16,
    "luk": 24,
    "jhn": 21,
    "act": 28,
    "rom": 16,
    "1co": 16,
    "2co": 13,
    "gal": 6,
    "eph": 6,
    "php": 4,
    "col": 4,
    "1th": 5,
    "2th": 3,
    "1ti": 6,
    "2ti": 4,
    "tit": 3,
    "phm": 1,
    "heb": 13,
    "jas": 5,
    "1pe": 5,
    "2pe": 3,
    "1jn": 5,
    "2jn": 1,
    "3jn": 1,
    "jud": 1,
    "rev": 22,
}

# Official GAE omissions we accept if live also omits them.
KNOWN_SOURCE_GAPS = {
    ("행", 24, 7),
}

REPORT = ROOT / "bible" / "full_audit_report.txt"
JSON_PATH = ROOT / "bible" / "gae_verses.json"

HANGUL_RE = re.compile(r"[\uAC00-\uD7A3]")
HTML_RE = re.compile(r"<[^>]+>|&nbsp;", re.I)


def _log(lines: list[str], message: str) -> None:
    lines.append(message)
    print(message, flush=True)


def _http_get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    raw = urllib.request.urlopen(request, timeout=30).read()
    for encoding in ("utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _fetch_live_chapter(book_code: str, chapter: int) -> dict[int, str]:
    url = (
        f"{BSKOREA_URL}?version=GAE&book={book_code}"
        f"&chap={chapter}&sec=1&sec2=300"
    )
    html = _http_get(url)
    section_match = re.search(r'id="tdBible1"(.*)', html, flags=re.DOTALL | re.IGNORECASE)
    section = section_match.group(1) if section_match else html
    verses: dict[int, str] = {}
    for match in VERSE_NUMBER_PATTERN.finditer(section):
        text = _clean_html_text(match.group(2))
        if not text:
            continue
        for verse_num in _parse_verse_number_token(match.group(1)):
            verses[verse_num] = text
    return verses


def structural_audit(data: dict, lines: list[str]) -> list[str]:
    errors: list[str] = []
    expected_keys = [book.aliases[0] for book in BOOKS]
    actual_keys = list(data.keys())

    if actual_keys != expected_keys:
        errors.append(f"BOOK_ORDER_OR_KEYS mismatch actual={actual_keys} expected={expected_keys}")
    _log(lines, f"books actual={len(actual_keys)} expected=66 order_ok={actual_keys == expected_keys}")

    total_verses = 0
    for book in BOOKS:
        ko = book.aliases[0]
        expected_chapters = CHAPTER_COUNTS[book.bskorea_code]
        book_map = data.get(ko)
        if not isinstance(book_map, dict):
            errors.append(f"MISSING_BOOK {ko}")
            continue

        chapter_keys = list(book_map.keys())
        expected_chapter_keys = [str(i) for i in range(1, expected_chapters + 1)]
        if chapter_keys != expected_chapter_keys:
            errors.append(
                f"CHAPTER_KEYS {ko}: got={chapter_keys[:5]}...{chapter_keys[-3:]} "
                f"expected_count={expected_chapters} actual_count={len(chapter_keys)}"
            )

        for chapter in range(1, expected_chapters + 1):
            chapter_key = str(chapter)
            verses = book_map.get(chapter_key)
            if not isinstance(verses, dict) or not verses:
                errors.append(f"EMPTY_CHAPTER {ko}:{chapter}")
                continue

            verse_keys = list(verses.keys())
            try:
                verse_nums = [int(key) for key in verse_keys]
            except ValueError:
                errors.append(f"BAD_VERSE_KEY {ko}:{chapter} keys={verse_keys[:10]}")
                continue

            if verse_keys != [str(num) for num in verse_nums]:
                errors.append(f"VERSE_KEY_NOT_STRINGIFIED {ko}:{chapter}")
            if verse_nums != sorted(verse_nums):
                errors.append(f"VERSE_ORDER {ko}:{chapter} keys={verse_nums[:20]}")
            if verse_nums[0] != 1:
                errors.append(f"VERSE_NOT_START_1 {ko}:{chapter} first={verse_nums[0]}")

            for verse_num in verse_nums:
                text = verses.get(str(verse_num))
                total_verses += 1
                if not isinstance(text, str) or not text.strip():
                    errors.append(f"EMPTY_VERSE {ko}:{chapter}:{verse_num}")
                    continue
                cleaned = text.strip()
                if HTML_RE.search(cleaned):
                    errors.append(f"HTML_RESIDUE {ko}:{chapter}:{verse_num}")
                if not HANGUL_RE.search(cleaned):
                    errors.append(f"NO_HANGUL {ko}:{chapter}:{verse_num} text={cleaned[:40]!r}")

            # Gaps inside 1..max, excluding known source gaps.
            present = set(verse_nums)
            for missing in range(1, max(verse_nums) + 1):
                if missing in present:
                    continue
                marker = (ko, chapter, missing)
                if marker not in KNOWN_SOURCE_GAPS:
                    errors.append(f"UNEXPECTED_GAP {ko}:{chapter}:{missing}")

    _log(lines, f"total_verses={total_verses}")
    return errors


def live_audit(data: dict, lines: list[str]) -> list[str]:
    """Compare every chapter to live bskorea. Retry transient failures."""
    errors: list[str] = []
    total = sum(CHAPTER_COUNTS[book.bskorea_code] for book in BOOKS)
    done = 0
    mismatches = 0
    fetch_failures = 0

    for book in BOOKS:
        ko = book.aliases[0]
        code = book.bskorea_code
        for chapter in range(1, CHAPTER_COUNTS[code] + 1):
            done += 1
            local_raw = (data.get(ko) or {}).get(str(chapter)) or {}
            local = {int(key): str(value).strip() for key, value in local_raw.items()}

            live: dict[int, str] | None = None
            last_error = ""
            for attempt in range(1, 5):
                try:
                    live = _fetch_live_chapter(code, chapter)
                    if live:
                        break
                    last_error = "empty live map"
                except Exception as error:
                    last_error = str(error)
                time.sleep(0.8 * attempt)

            if not live:
                fetch_failures += 1
                errors.append(f"LIVE_FETCH_FAIL {ko}:{chapter} code={code} err={last_error}")
                _log(lines, f"[{done}/{total}] FAIL fetch {ko}:{chapter}")
                time.sleep(0.25)
                continue

            local_keys = sorted(local)
            live_keys = sorted(live)
            missing_in_local = [num for num in live_keys if num not in local]
            extra_in_local = [num for num in local_keys if num not in live]
            text_mismatch = [
                num
                for num in live_keys
                if num in local and local[num] != live[num]
            ]

            # Accept known source gaps only when live also lacks them.
            for ko_g, ch_g, vs_g in KNOWN_SOURCE_GAPS:
                if ko_g == ko and ch_g == chapter and vs_g in extra_in_local:
                    # local has a verse live doesn't - still an error
                    pass

            if missing_in_local or extra_in_local or text_mismatch:
                mismatches += 1
                detail = (
                    f"LIVE_MISMATCH {ko}:{chapter} "
                    f"missing_in_local={missing_in_local} "
                    f"extra_in_local={extra_in_local} "
                    f"text_mismatch={text_mismatch[:10]}"
                )
                errors.append(detail)
                if text_mismatch:
                    num = text_mismatch[0]
                    errors.append(
                        f"  TEXT {ko}:{chapter}:{num} "
                        f"live={live[num][:60]!r} local={local[num][:60]!r}"
                    )
                _log(lines, f"[{done}/{total}] MISMATCH {ko}:{chapter}")
            elif done % 25 == 0 or chapter == CHAPTER_COUNTS[code]:
                _log(
                    lines,
                    f"[{done}/{total}] OK {ko}:{chapter} verses={len(live)}",
                )

            time.sleep(0.22)

    _log(
        lines,
        f"live_summary mismatches={mismatches} fetch_failures={fetch_failures} checked={done}",
    )
    return errors


def main() -> int:
    lines: list[str] = []
    _log(lines, f"=== FULL AUDIT START {JSON_PATH} ===")

    if not JSON_PATH.is_file():
        _log(lines, "FATAL: JSON file missing")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        return 1

    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception as error:
        _log(lines, f"FATAL: JSON parse failed: {error}")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        return 1

    if not isinstance(data, dict):
        _log(lines, "FATAL: root is not an object")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        return 1

    structural_errors = structural_audit(data, lines)
    live_errors = live_audit(data, lines)
    all_errors = structural_errors + live_errors

    _log(lines, "=== RESULT ===")
    if all_errors:
        _log(lines, f"FAILED error_count={len(all_errors)}")
        for item in all_errors[:200]:
            _log(lines, item)
        if len(all_errors) > 200:
            _log(lines, f"... and {len(all_errors) - 200} more")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        return 1

    _log(lines, "PASSED: structure + full live bskorea chapter compare OK")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
