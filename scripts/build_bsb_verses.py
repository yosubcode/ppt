"""Build bible/bsb_verses.json from official BSB USJ (public domain).

Output format matches bible/gae_verses.json:
  { "<ko-book>": { "<chapter>": { "<verse>": "<text>" } } }

Does not wire the file into the app.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIP_URL = "https://github.com/BSB-publishing/bsb2usfm/releases/download/v5.12/BSB_usj.zip"
TMP_DIR = ROOT / "bible" / "_bsb_tmp"
ZIP_PATH = TMP_DIR / "BSB_usj.zip"
OUT_PATH = ROOT / "bible" / "bsb_verses.json"

USFM_TO_KO: list[tuple[str, str]] = [
    ("GEN", "창"),
    ("EXO", "출"),
    ("LEV", "레"),
    ("NUM", "민"),
    ("DEU", "신"),
    ("JOS", "수"),
    ("JDG", "삿"),
    ("RUT", "룻"),
    ("1SA", "삼상"),
    ("2SA", "삼하"),
    ("1KI", "왕상"),
    ("2KI", "왕하"),
    ("1CH", "대상"),
    ("2CH", "대하"),
    ("EZR", "스"),
    ("NEH", "느"),
    ("EST", "에"),
    ("JOB", "욥"),
    ("PSA", "시"),
    ("PRO", "잠"),
    ("ECC", "전"),
    ("SNG", "아"),
    ("ISA", "사"),
    ("JER", "렘"),
    ("LAM", "애"),
    ("EZK", "겔"),
    ("DAN", "단"),
    ("HOS", "호"),
    ("JOL", "욜"),
    ("AMO", "암"),
    ("OBA", "옵"),
    ("JON", "욘"),
    ("MIC", "미"),
    ("NAM", "나"),
    ("HAB", "합"),
    ("ZEP", "습"),
    ("HAG", "학"),
    ("ZEC", "슥"),
    ("MAL", "말"),
    ("MAT", "마"),
    ("MRK", "막"),
    ("LUK", "눅"),
    ("JHN", "요"),
    ("ACT", "행"),
    ("ROM", "롬"),
    ("1CO", "고전"),
    ("2CO", "고후"),
    ("GAL", "갈"),
    ("EPH", "엡"),
    ("PHP", "빌"),
    ("COL", "골"),
    ("1TH", "살전"),
    ("2TH", "살후"),
    ("1TI", "딤전"),
    ("2TI", "딤후"),
    ("TIT", "딛"),
    ("PHM", "몬"),
    ("HEB", "히"),
    ("JAS", "약"),
    ("1PE", "벧전"),
    ("2PE", "벧후"),
    ("1JN", "요일"),
    ("2JN", "요이"),
    ("3JN", "요삼"),
    ("JUD", "유"),
    ("REV", "계"),
]

# Skip pure titles/refs. Keep "d" (Psalm superscriptions often hold verse 1).
HEADING_MARKERS = {
    "s",
    "s1",
    "s2",
    "s3",
    "s4",
    "ms",
    "ms1",
    "ms2",
    "mr",
    "sr",
    "r",
    "sp",
    "qa",
    "qc",
    "cl",
    "cd",
    "toc1",
    "toc2",
    "toc3",
    "h",
    "mt",
    "mt1",
    "mt2",
    "mt3",
    "mte",
    "mte1",
    "imt",
    "imt1",
    "is",
    "is1",
    "ip",
    "iot",
    "io",
    "io1",
    "io2",
    "id",
    "ide",
    "rem",
    "sts",
}

SPACE_RE = re.compile(r"\s+")
GLUE_RE = re.compile(r'([.!?,:;)"”\'’\]])([A-Za-z“"\'])')
WORD_GLUE_RE = re.compile(r"([a-z])([A-Z])")


def normalize(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = SPACE_RE.sub(" ", text).strip()
    for _ in range(3):
        updated = GLUE_RE.sub(r"\1 \2", text)
        updated = WORD_GLUE_RE.sub(r"\1 \2", updated)
        if updated == text:
            break
        text = updated
    return text.strip()


def parse_usj(data: dict) -> dict[str, dict[str, str]]:
    chapters: dict[str, dict[str, str]] = {}
    chapter: str | None = None
    verse: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal verse, buf
        if chapter is None or verse is None:
            buf = []
            return
        text = normalize("".join(buf))
        if text:
            chapters.setdefault(chapter, {})[verse] = text
        buf = []

    def append_text(piece: str) -> None:
        if not piece or verse is None:
            return
        if buf:
            prev = buf[-1]
            if prev and piece:
                left = prev[-1]
                right = piece[0]
                if left.isalnum() and right.isalnum():
                    buf.append(" ")
                elif left in ".!?,:;)]}”’\"'" and (right.isalnum() or right in "“\"'"):
                    buf.append(" ")
        buf.append(piece)

    def walk(nodes) -> None:
        nonlocal chapter, verse, buf
        for node in nodes:
            if isinstance(node, str):
                append_text(node)
                continue
            if not isinstance(node, dict):
                continue

            ntype = node.get("type")
            marker = str(node.get("marker") or "")

            if ntype == "chapter":
                flush()
                chapter = str(node.get("number", "")).strip()
                verse = None
                continue

            if ntype == "verse":
                flush()
                verse = str(node.get("number", "")).strip()
                continue

            if ntype == "note":
                continue

            if ntype == "para" and (
                marker in HEADING_MARKERS
                or marker.startswith(("s", "ms", "mt", "imt", "io", "is"))
            ):
                continue

            # Poetry/paragraph breaks: ensure a space before the next line body.
            if ntype == "para" and verse is not None and buf and not str(buf[-1]).endswith((" ", "\n")):
                buf.append(" ")

            content = node.get("content")
            if isinstance(content, list):
                walk(content)

    walk(data.get("content") or [])
    flush()
    return chapters


def main() -> int:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    if not ZIP_PATH.exists():
        print(f"Downloading {ZIP_URL}")
        urllib.request.urlretrieve(ZIP_URL, ZIP_PATH)

    payload: dict[str, dict[str, dict[str, str]]] = {}
    with zipfile.ZipFile(ZIP_PATH) as zf:
        names = {
            Path(name).stem.upper(): name
            for name in zf.namelist()
            if name.upper().endswith(".USJ")
        }
        for code, ko in USFM_TO_KO:
            if code not in names:
                raise SystemExit(f"Missing USJ book: {code}")
            book_data = json.loads(zf.read(names[code]))
            payload[ko] = parse_usj(book_data)
            verse_count = sum(len(ch) for ch in payload[ko].values())
            print(f"{code} -> {ko}: {len(payload[ko])} ch, {verse_count} verses")

    # Match bible/gae_verses.json readability (indent=2, keep Hangul/Unicode).
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    total = sum(len(v) for book in payload.values() for v in book.values())
    print(f"Wrote {OUT_PATH} ({total} verses, {OUT_PATH.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
