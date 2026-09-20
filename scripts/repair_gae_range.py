"""Audit and repair gae_verses.json for a book range against bskorea 개역개정."""

from __future__ import annotations

import json
import sys
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from bible_books import BOOKS  # noqa: E402
from bible_fetcher import _fetch_korean_bskorea  # noqa: E402
from scrape_gae_bible import CHAPTER_COUNTS, _sorted_bible  # noqa: E402
from scripture_parser import ScriptureRange  # noqa: E402

OUTPUT_PATH = ROOT / "bible" / "gae_verses.json"
CHAPTER_GAP_SECONDS = 0.3
MAX_ATTEMPTS = 5


def _books_in_range(start_name: str, end_name: str):
    started = False
    selected = []
    for book in BOOKS:
        if book.english_name == start_name:
            started = True
        if not started:
            continue
        selected.append(book)
        if book.english_name == end_name:
            break
    return selected


def _fetch_chapter(book_code: str, chapter: int) -> dict[int, str]:
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = _fetch_korean_bskorea(
                book_code, ScriptureRange(book=None, chapter=chapter, start=1, end=300)
            )
            cleaned = {
                num: text.strip()
                for num, text in raw.items()
                if text and str(text).strip()
            }
            if not cleaned:
                raise RuntimeError("empty verse map")
            numbers = sorted(cleaned)
            # Some GAE chapters omit verses (e.g. Acts 24:7). Keep site order as-is.
            if numbers[0] != 1:
                raise RuntimeError(f"does not start at 1: {numbers[:5]}")
            return cleaned
        except Exception as error:
            last_error = str(error)
            time.sleep(min(12.0, 1.2 * attempt))
    raise RuntimeError(last_error)


def _chapter_differs(local: dict | None, remote: dict[int, str]) -> bool:
    if not isinstance(local, dict) or not local:
        return True
    try:
        local_nums = sorted(int(key) for key in local.keys())
    except ValueError:
        return True
    remote_nums = sorted(remote.keys())
    if local_nums != remote_nums:
        return True
    for num in remote_nums:
        if str(local.get(str(num), "")).strip() != remote[num].strip():
            return True
    if local_nums != list(range(1, len(local_nums) + 1)):
        return True
    if list(local.keys()) != [str(n) for n in local_nums]:
        return True
    return False


def audit_and_repair(start_name: str = "Lamentations", end_name: str = "1 Peter") -> None:
    books = _books_in_range(start_name, end_name)
    data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))

    print(f"Range: {books[0].aliases[0]} .. {books[-1].aliases[0]} ({len(books)} books)")

    # Structural scan
    struct_issues: list[str] = []
    for book in books:
        ko = book.aliases[0]
        expected = list(range(1, CHAPTER_COUNTS[book.bskorea_code] + 1))
        book_map = data.get(ko)
        if not isinstance(book_map, dict):
            struct_issues.append(f"{ko}: missing book")
            continue
        present = [int(key) for key in book_map.keys()]
        if present != expected:
            struct_issues.append(
                f"{ko}: chapter order/missing present={present} expected={expected}"
            )
        for chapter in expected:
            chapter_map = book_map.get(str(chapter))
            if not isinstance(chapter_map, dict) or not chapter_map:
                struct_issues.append(f"{ko}:{chapter}: missing")
                continue
            verse_nums = [int(key) for key in chapter_map.keys()]
            if verse_nums != list(range(1, len(verse_nums) + 1)):
                struct_issues.append(f"{ko}:{chapter}: verse order/gaps {verse_nums}")

    print(f"Structural issues before repair: {len(struct_issues)}")
    for item in struct_issues[:40]:
        print(" ", item)

    repaired: list[str] = []
    failed: list[str] = []
    checked = 0

    for book in books:
        ko = book.aliases[0]
        code = book.bskorea_code
        chapter_count = CHAPTER_COUNTS[code]
        book_map = data.setdefault(ko, {})
        if not isinstance(book_map, dict):
            book_map = {}
            data[ko] = book_map

        print(f"Scan {ko} ({book.english_name}) {chapter_count} chapters")
        for chapter in range(1, chapter_count + 1):
            checked += 1
            chapter_key = str(chapter)
            local = book_map.get(chapter_key)

            # Always fetch to validate content against bskorea.
            try:
                remote = _fetch_chapter(code, chapter)
            except Exception as error:
                failed.append(f"{ko}:{chapter}: {error}")
                print(f"  FAIL {ko} ch{chapter}: {error}")
                time.sleep(CHAPTER_GAP_SECONDS)
                continue

            if _chapter_differs(local, remote):
                book_map[chapter_key] = {
                    str(num): remote[num] for num in sorted(remote)
                }
                repaired.append(f"{ko}:{chapter} ({len(remote)} verses)")
                print(f"  FIX {ko} ch{chapter}: {len(remote)} verses")
                # Persist frequently so progress is not lost.
                OUTPUT_PATH.write_text(
                    json.dumps(_sorted_bible(data), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            else:
                # Ensure key order even when content matches.
                ordered_local = {str(num): local[str(num)] for num in sorted(int(k) for k in local)}
                if list(local.keys()) != list(ordered_local.keys()):
                    book_map[chapter_key] = ordered_local
                    repaired.append(f"{ko}:{chapter} order-only")
                    print(f"  ORDER {ko} ch{chapter}")
                else:
                    print(f"  OK {ko} ch{chapter}: {len(remote)}")

            time.sleep(CHAPTER_GAP_SECONDS)

        # Keep chapters sorted within book after each book.
        data[ko] = {
            str(ch): book_map[str(ch)]
            for ch in sorted(int(key) for key in book_map.keys())
            if str(ch) in book_map
        }
        OUTPUT_PATH.write_text(
            json.dumps(_sorted_bible(data), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # Final sorted write
    OUTPUT_PATH.write_text(
        json.dumps(_sorted_bible(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"DONE checked={checked} repaired={len(repaired)} failed={len(failed)}")
    if repaired:
        print("Repaired:")
        for item in repaired:
            print(" ", item)
    if failed:
        print("Failed:")
        for item in failed:
            print(" ", item)
        raise SystemExit(1)


if __name__ == "__main__":
    start = "Lamentations"
    end = "1 Peter"
    if len(sys.argv) >= 3:
        start, end = sys.argv[1], sys.argv[2]
    audit_and_repair(start, end)
