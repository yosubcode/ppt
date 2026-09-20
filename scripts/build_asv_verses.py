"""Build bible/asv_verses.json from public-domain American Standard Version (ASV).

Output format matches bible/gae_verses.json / bible/bsb_verses.json / bible/web_verses.json:
  { "<ko-book>": { "<chapter>": { "<verse>": "<text>" } } }

Does not wire the file into the app.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_URL = (
    "https://raw.githubusercontent.com/midvash/bible-data/main/versions/en/asv/asv.json"
)
TMP_DIR = ROOT / "bible" / "_asv_tmp"
CACHE_PATH = TMP_DIR / "asv.json"
OUT_PATH = ROOT / "bible" / "asv_verses.json"

# OSIS-style book codes from midvash ASV -> Korean short keys (gae order)
BOOK_TO_KO: list[tuple[str, str]] = [
    ("Gen", "창"),
    ("Exod", "출"),
    ("Lev", "레"),
    ("Num", "민"),
    ("Deut", "신"),
    ("Josh", "수"),
    ("Judg", "삿"),
    ("Ruth", "룻"),
    ("1Sam", "삼상"),
    ("2Sam", "삼하"),
    ("1Kgs", "왕상"),
    ("2Kgs", "왕하"),
    ("1Chr", "대상"),
    ("2Chr", "대하"),
    ("Ezra", "스"),
    ("Neh", "느"),
    ("Esth", "에"),
    ("Job", "욥"),
    ("Ps", "시"),
    ("Prov", "잠"),
    ("Eccl", "전"),
    ("Song", "아"),
    ("Isa", "사"),
    ("Jer", "렘"),
    ("Lam", "애"),
    ("Ezek", "겔"),
    ("Dan", "단"),
    ("Hos", "호"),
    ("Joel", "욜"),
    ("Amos", "암"),
    ("Obad", "옵"),
    ("Jonah", "욘"),
    ("Mic", "미"),
    ("Nah", "나"),
    ("Hab", "합"),
    ("Zeph", "습"),
    ("Hag", "학"),
    ("Zech", "슥"),
    ("Mal", "말"),
    ("Matt", "마"),
    ("Mark", "막"),
    ("Luke", "눅"),
    ("John", "요"),
    ("Acts", "행"),
    ("Rom", "롬"),
    ("1Cor", "고전"),
    ("2Cor", "고후"),
    ("Gal", "갈"),
    ("Eph", "엡"),
    ("Phil", "빌"),
    ("Col", "골"),
    ("1Thess", "살전"),
    ("2Thess", "살후"),
    ("1Tim", "딤전"),
    ("2Tim", "딤후"),
    ("Titus", "딛"),
    ("Phlm", "몬"),
    ("Heb", "히"),
    ("Jas", "약"),
    ("1Pet", "벧전"),
    ("2Pet", "벧후"),
    ("1John", "요일"),
    ("2John", "요이"),
    ("3John", "요삼"),
    ("Jude", "유"),
    ("Rev", "계"),
]

SPACE_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    return SPACE_RE.sub(" ", text.replace("\u00a0", " ")).strip()


def convert(source: dict) -> dict[str, dict[str, dict[str, str]]]:
    by_code = {str(book.get("book")): book for book in source.get("books", [])}
    payload: dict[str, dict[str, dict[str, str]]] = {}

    for code, ko in BOOK_TO_KO:
        book = by_code.get(code)
        if book is None:
            raise SystemExit(f"Missing ASV book: {code}")

        chapters: dict[str, dict[str, str]] = {}
        for chapter in book.get("chapters") or []:
            chapter_num = str(chapter.get("chapter", "")).strip()
            if not chapter_num:
                continue
            verses: dict[str, str] = {}
            for verse in chapter.get("verses") or []:
                verse_num = str(verse.get("number", "")).strip()
                text = normalize(str(verse.get("text", "")))
                if verse_num and text:
                    verses[verse_num] = text
            if verses:
                chapters[chapter_num] = verses

        payload[ko] = chapters
        verse_count = sum(len(ch) for ch in chapters.values())
        print(f"{code} -> {ko}: {len(chapters)} ch, {verse_count} verses")

    return payload


def main() -> int:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    if not CACHE_PATH.exists():
        print(f"Downloading {SOURCE_URL}")
        urllib.request.urlretrieve(SOURCE_URL, CACHE_PATH)

    source = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    payload = convert(source)

    gae_path = ROOT / "bible" / "gae_verses.json"
    if gae_path.exists():
        gae = json.loads(gae_path.read_text(encoding="utf-8"))
        if list(payload.keys()) != list(gae.keys()):
            raise SystemExit("Book key order does not match gae_verses.json")

    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    total = sum(len(v) for book in payload.values() for v in book.values())
    print(f"Wrote {OUT_PATH} ({total} verses, {OUT_PATH.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
