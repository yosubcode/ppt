"""Scrape full 개역개정 text from bskorea into bible/gae_verses.json.

Keys use Korean book abbreviations (창, 막, ...). Supports resume and gap repair.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bible_books import BOOKS
from bible_fetcher import (
    _fetch_korean_bskorea,
    _fetch_korean_holybible,
)
from scripture_parser import ScriptureRange

OUTPUT_PATH = ROOT / "bible" / "gae_verses.json"
LOG_PATH = ROOT / "bible" / "scrape_log.txt"
FAIL_PATH = ROOT / "bible" / "scrape_failures.json"

# Protestant canon chapter counts.
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

CHAPTER_GAP_SECONDS = 0.35
MAX_CHAPTER_ATTEMPTS = 6


def _log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = message.rstrip() + "\n"
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line)
    print(line, end="", flush=True)


def _load_bible() -> dict:
    if OUTPUT_PATH.is_file():
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    return {}


def _korean_key(book) -> str:
    return book.aliases[0]


def _sorted_bible(data: dict) -> dict:
    """Return bible data with books in canon order and numeric chapter/verse keys."""
    ordered: dict = {}
    seen: set[str] = set()
    for book in BOOKS:
        ko_key = _korean_key(book)
        book_map = data.get(ko_key)
        if not isinstance(book_map, dict):
            continue
        seen.add(ko_key)
        chapters: dict = {}
        for chapter in sorted(book_map.keys(), key=lambda key: int(key)):
            verse_map = book_map[chapter]
            if not isinstance(verse_map, dict):
                continue
            chapters[str(int(chapter))] = {
                str(verse): verse_map[str(verse)]
                for verse in sorted(int(key) for key in verse_map.keys())
            }
        ordered[ko_key] = chapters
    for ko_key, book_map in data.items():
        if ko_key in seen or not isinstance(book_map, dict):
            continue
        chapters = {}
        try:
            chapter_keys = sorted(book_map.keys(), key=lambda key: int(key))
        except ValueError:
            chapter_keys = list(book_map.keys())
        for chapter in chapter_keys:
            verse_map = book_map[chapter]
            if not isinstance(verse_map, dict):
                continue
            try:
                verse_keys = sorted(int(key) for key in verse_map.keys())
                chapters[str(int(chapter))] = {
                    str(verse): verse_map[str(verse)] for verse in verse_keys
                }
            except ValueError:
                chapters[str(chapter)] = verse_map
        ordered[ko_key] = chapters
    return ordered


def _save_bible(data: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(_sorted_bible(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _chapter_complete(chapter_map: dict | None) -> bool:
    """True when chapter has usable verses starting at 1.

    Some GAE chapters intentionally omit verses (e.g. Acts 24:7), so gaps are allowed.
    """
    if not isinstance(chapter_map, dict) or not chapter_map:
        return False
    try:
        numbers = sorted(int(key) for key in chapter_map.keys())
    except ValueError:
        return False
    if not numbers or numbers[0] != 1:
        return False
    return all(str(chapter_map[str(num)]).strip() for num in numbers)


def _fetch_full_chapter(book_code: str, chapter: int) -> dict[int, str]:
    """Fetch one full chapter; try bskorea then holybible backends."""
    # Request a wide verse window so the page returns the whole chapter.
    wide_range = ScriptureRange(book=None, chapter=chapter, start=1, end=300)
    errors: list[str] = []

    for source_name, fetcher in (
        ("bskorea", _fetch_korean_bskorea),
        ("holybible-GAE", lambda code, rng: _fetch_korean_holybible(code, rng, vr="GAE")),
        ("holybible-VR9", lambda code, rng: _fetch_korean_holybible(code, rng, vr="9")),
    ):
        try:
            raw = fetcher(book_code, wide_range)
            if not raw:
                raise RuntimeError("empty verse map")
            # Keep whatever verses the page actually has (full chapter).
            cleaned = {
                verse_num: text.strip()
                for verse_num, text in raw.items()
                if text and str(text).strip()
            }
            if not cleaned:
                raise RuntimeError("all verses empty after cleanup")
            numbers = sorted(cleaned)
            # GAE may omit some verse numbers (textual tradition); require start at 1 only.
            if numbers[0] != 1:
                raise RuntimeError(f"chapter does not start at verse 1: {numbers[:5]}")
            return cleaned
        except Exception as error:
            errors.append(f"{source_name}: {error}")

    raise RuntimeError(" | ".join(errors))


def _scrape_chapter_with_retries(book_code: str, chapter: int) -> dict[int, str]:
    last_error = ""
    for attempt in range(1, MAX_CHAPTER_ATTEMPTS + 1):
        try:
            return _fetch_full_chapter(book_code, chapter)
        except Exception as error:
            last_error = str(error)
            wait = min(20.0, 1.2 * attempt)
            _log(
                f"  BLOCKED/FAIL {book_code} ch{chapter} "
                f"attempt {attempt}/{MAX_CHAPTER_ATTEMPTS}: {last_error} "
                f"(wait {wait:.1f}s)"
            )
            time.sleep(wait)
    raise RuntimeError(last_error)


def scrape_all(*, repair_only: bool = False) -> int:
    bible = _load_bible()
    failures: list[dict] = []
    total_chapters = sum(CHAPTER_COUNTS[book.bskorea_code] for book in BOOKS)
    done_chapters = 0

    _log(f"=== scrape start repair_only={repair_only} total_chapters={total_chapters} ===")

    for book in BOOKS:
        ko_key = _korean_key(book)
        chapter_count = CHAPTER_COUNTS[book.bskorea_code]
        book_map = bible.setdefault(ko_key, {})
        if not isinstance(book_map, dict):
            book_map = {}
            bible[ko_key] = book_map

        for chapter in range(1, chapter_count + 1):
            chapter_key = str(chapter)
            existing = book_map.get(chapter_key)
            if _chapter_complete(existing):
                done_chapters += 1
                if repair_only:
                    continue
                # Resume: skip completed chapters.
                continue

            if repair_only or existing:
                _log(f"Repair {ko_key} {chapter}/{chapter_count} ({book.english_name})")
            else:
                _log(f"Scrape {ko_key} {chapter}/{chapter_count} ({book.english_name})")

            try:
                verses = _scrape_chapter_with_retries(book.bskorea_code, chapter)
                book_map[chapter_key] = {
                    str(verse_num): text for verse_num, text in sorted(verses.items())
                }
                _save_bible(bible)
                done_chapters += 1
                _log(
                    f"  OK {ko_key} ch{chapter}: {len(verses)} verses "
                    f"({done_chapters}/{total_chapters})"
                )
            except Exception as error:
                failures.append(
                    {
                        "book_ko": ko_key,
                        "book_code": book.bskorea_code,
                        "chapter": chapter,
                        "error": str(error),
                        "trace": traceback.format_exc(limit=3),
                    }
                )
                _log(f"  GIVE UP {ko_key} ch{chapter}: {error}")

            time.sleep(CHAPTER_GAP_SECONDS)

    FAIL_PATH.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"=== pass done failures={len(failures)} ===")
    return len(failures)


def verify_and_repair(max_rounds: int = 5) -> None:
    """Keep repairing until every expected chapter is present and contiguous."""
    for round_index in range(1, max_rounds + 1):
        bible = _load_bible()
        missing: list[tuple[str, str, int]] = []
        for book in BOOKS:
            ko_key = _korean_key(book)
            book_map = bible.get(ko_key) if isinstance(bible.get(ko_key), dict) else {}
            for chapter in range(1, CHAPTER_COUNTS[book.bskorea_code] + 1):
                if not _chapter_complete(book_map.get(str(chapter))):
                    missing.append((ko_key, book.bskorea_code, chapter))

        _log(f"Verify round {round_index}: missing_chapters={len(missing)}")
        if not missing:
            _log("VERIFY OK: all chapters present with contiguous verses")
            FAIL_PATH.write_text("[]\n", encoding="utf-8")
            return

        # Clear incomplete chapters so scrape retries them.
        for ko_key, _code, chapter in missing:
            book_map = bible.setdefault(ko_key, {})
            book_map.pop(str(chapter), None)
        _save_bible(bible)

        scrape_all(repair_only=True)

    bible = _load_bible()
    still_missing = []
    for book in BOOKS:
        ko_key = _korean_key(book)
        book_map = bible.get(ko_key) if isinstance(bible.get(ko_key), dict) else {}
        for chapter in range(1, CHAPTER_COUNTS[book.bskorea_code] + 1):
            if not _chapter_complete(book_map.get(str(chapter))):
                still_missing.append(f"{ko_key}:{chapter}")
    if still_missing:
        raise SystemExit(
            "Scrape incomplete after repairs. Missing: " + ", ".join(still_missing[:40])
        )


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists() and "--fresh-log" in sys.argv:
        LOG_PATH.write_text("", encoding="utf-8")

    scrape_all(repair_only=False)
    verify_and_repair(max_rounds=5)

    bible = _load_bible()
    book_count = len(bible)
    chapter_count = sum(len(chapters) for chapters in bible.values() if isinstance(chapters, dict))
    verse_count = sum(
        len(verses)
        for chapters in bible.values()
        if isinstance(chapters, dict)
        for verses in chapters.values()
        if isinstance(verses, dict)
    )
    _log(
        f"DONE books={book_count} chapters={chapter_count} verses={verse_count} "
        f"output={OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
