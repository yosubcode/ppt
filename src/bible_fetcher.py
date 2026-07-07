"""Fetch scripture references and verse text for slide generation."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from bible_books import (
    format_scripture_reference_en,
    format_scripture_reference_ko_full,
    resolve_bible_book,
)
from scripture_parser import ScriptureRange, apply_scripture_range_to_data, parse_scripture_range
from sermon_verse_parser import build_sermon_part_ko_en, format_part_verse_ref_en

USER_AGENT = "Mozilla/5.0 (WorshipPPT/1.0)"
BSKOREA_URL = "https://www.bskorea.or.kr/bible/korbibReadpage.php"
BIBLE_API_URL = "https://bible-api.com"
ESV_API_URL = "https://api.esv.org/v3/passage/text/"

VERSE_NUMBER_PATTERN = re.compile(
    r'<span class="number"[^>]*>(?:<a[^>]*></a>)?(\d+)&nbsp;.*?</span>(.*?)</span>',
    re.DOTALL,
)


def enrich_scripture_data(data: dict[str, Any], *, fetch: bool = True) -> dict[str, Any]:
    """Fill slide reference labels and optional verse bulk text from the bulletin reference."""
    updated = apply_scripture_range_to_data(data)
    scripture = str(updated.get("scripture", "")).strip()
    if not scripture:
        return updated

    reference_ko = format_scripture_reference_ko_full(scripture)
    reference_en = format_scripture_reference_en(scripture)
    updated["scripture_ko"] = reference_ko
    if reference_en:
        updated["scripture_en"] = reference_en
        updated["scripture_reference"] = reference_en

    has_manual_text = bool(
        str(updated.get("scripture_ko_text", "")).strip()
        or str(updated.get("scripture_en_text", "")).strip()
    )
    if not fetch or has_manual_text:
        return updated

    parsed = _resolve_range(updated)
    book = resolve_bible_book(scripture, parsed)
    if not parsed or not book or not reference_en:
        return updated

    try:
        ko_map = fetch_korean_verses(book.bskorea_code, parsed)
        en_map = fetch_english_verses(reference_en, parsed)
    except Exception:
        return updated

    if ko_map:
        updated["scripture_ko_text"] = _join_verse_map(ko_map, include_numbers=False)
    if en_map:
        updated["scripture_en_text"] = _join_verse_map(en_map, include_numbers=False)

    return updated


def enrich_sermon_part_verses(data: dict[str, Any], *, fetch: bool = True) -> dict[str, Any]:
    """Fill sermon part verse REF/KO/EN fields from parsed PDF quotes and bible fetch."""
    updated = apply_scripture_range_to_data(data)
    parts = updated.get("_sermon_part_verses")
    if not isinstance(parts, dict) or not parts:
        return updated

    chapter = updated.get("scripture_chapter")
    if chapter is None:
        return updated

    scripture = str(updated.get("scripture", "")).strip()
    book = resolve_bible_book(scripture)
    book_en = book.english_name if book else ""

    for index in (1, 2, 3):
        part = parts.get(index) or parts.get(str(index))
        if not isinstance(part, dict):
            continue

        start = int(part["verse_start"])
        end = int(part["verse_end"])
        verse_range = ScriptureRange(book=None, chapter=int(chapter), start=start, end=end)

        if start == end:
            ref_ko = f"{chapter}:{start}"
        else:
            ref_ko = f"{chapter}:{start}-{end}"
        ref_en = format_part_verse_ref_en(book_en, int(chapter), start, end) if book_en else ref_ko

        pdf_ko = str(part.get("verse_ko_quote", "")).strip()
        ko_text = ""
        en_text = ""
        if fetch and book:
            try:
                ko_map = fetch_korean_verses(book.bskorea_code, verse_range)
                en_map = fetch_english_verses(ref_en, verse_range)
                if pdf_ko:
                    ko_text, en_text = build_sermon_part_ko_en(
                        pdf_ko,
                        ko_map,
                        en_map,
                        truncated=bool(part.get("verse_ko_truncated")),
                    )
                else:
                    ko_text = _join_verse_map(ko_map, include_numbers=False, separator=" ")
                    en_text = _join_verse_map(en_map, include_numbers=False, separator=" ")
            except Exception:
                ko_text = ""
                en_text = ""

        if not ko_text and pdf_ko:
            ko_text = pdf_ko

        updated[f"verse_ref{index}"] = ref_ko
        updated[f"verse_ko{index}"] = ko_text
        updated[f"verse_en{index}"] = en_text

    updated.pop("_sermon_part_verses", None)
    return updated


def fetch_korean_verses(book_code: str, scripture_range: ScriptureRange) -> dict[int, str]:
    """Fetch 개역개정 verses from bskorea.or.kr."""
    url = (
        f"{BSKOREA_URL}?version=GAE&book={book_code}"
        f"&chap={scripture_range.chapter}"
        f"&sec={scripture_range.start}&sec2={scripture_range.end}"
    )
    html = _http_get(url)
    section_match = re.search(r'id="tdBible1"(.*)', html, flags=re.DOTALL | re.IGNORECASE)
    section = section_match.group(1) if section_match else html

    verses: dict[int, str] = {}
    for match in VERSE_NUMBER_PATTERN.finditer(section):
        verse_num = int(match.group(1))
        if verse_num < scripture_range.start or verse_num > scripture_range.end:
            continue
        text = _clean_html_text(match.group(2))
        if text:
            verses[verse_num] = text

    if len(verses) != scripture_range.count:
        missing = [num for num in scripture_range.verse_numbers() if num not in verses]
        if missing:
            raise ValueError(f"Missing Korean verses: {missing}")
    return verses


def fetch_english_verses(reference_en: str, scripture_range: ScriptureRange) -> dict[int, str]:
    """Fetch English verses, preferring ESV when configured."""
    esv_map = _fetch_esv_verses(reference_en)
    if esv_map:
        return esv_map

    openai_map = _fetch_openai_esv_verses(reference_en, scripture_range)
    if openai_map:
        return openai_map

    query = urllib.parse.quote(reference_en.replace(" ", "+"))
    url = f"{BIBLE_API_URL}/{query}?translation=web"
    payload = json.loads(_http_get(url))
    verses: dict[int, str] = {}
    for item in payload.get("verses", []):
        verse_num = int(item.get("verse", 0))
        text = str(item.get("text", "")).strip()
        if verse_num and text:
            verses[verse_num] = _normalize_spaces(text)
    if not verses and payload.get("text"):
        return _split_plain_passage(payload["text"], scripture_range)
    return verses


def _fetch_esv_verses(reference_en: str) -> dict[int, str]:
    api_key = os.getenv("ESV_API_KEY", "").strip()
    if not api_key:
        return {}

    query = urllib.parse.urlencode(
        {
            "q": reference_en,
            "include-headings": "false",
            "include-footnotes": "false",
            "include-verse-numbers": "true",
            "include-short-copyright": "false",
            "include-passage-references": "false",
        }
    )
    request = urllib.request.Request(
        f"{ESV_API_URL}?{query}",
        headers={"Authorization": f"Token {api_key}", "User-Agent": USER_AGENT},
    )
    try:
        payload = json.loads(urllib.request.urlopen(request, timeout=20).read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return {}

    passage = str(payload.get("passages", [""])[0]).strip()
    if not passage:
        return {}

    from scripture_parser import parse_scripture_range, split_bulk_verse_text

    scripture_range = parse_scripture_range(reference_en)
    verses = split_bulk_verse_text(passage, scripture_range)
    if verses:
        return verses
    return {}


def _fetch_openai_esv_verses(
    reference_en: str,
    scripture_range: ScriptureRange,
) -> dict[int, str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {}

    from translator import _translate_with_openai

    numbered = "\n".join(
        f"{verse_num}. [Provide ESV text for {reference_en}, verse {verse_num} only]"
        for verse_num in scripture_range.verse_numbers()
    )
    translated = _translate_with_openai(
        numbered,
        api_key,
        system_prompt=(
            "Return only the ESV (English Standard Version) text for each numbered verse. "
            "Keep one verse per numbered line in the form '6. Verse text'. "
            "Use ESV wording exactly where possible."
        ),
    )
    verses: dict[int, str] = {}
    for match in re.finditer(r"^\s*(\d+)\.\s*(.+)$", translated, flags=re.MULTILINE):
        verses[int(match.group(1))] = _normalize_spaces(match.group(2))
    return verses


def _split_plain_passage(text: str, scripture_range: ScriptureRange) -> dict[int, str]:
    parts = [part.strip() for part in text.split("\n") if part.strip()]
    if len(parts) != scripture_range.count:
        return {}
    return {
        verse_num: parts[index]
        for index, verse_num in enumerate(scripture_range.verse_numbers())
    }


def _join_verse_map(
    verse_map: dict[int, str],
    *,
    include_numbers: bool,
    separator: str = "\n\n",
) -> str:
    lines: list[str] = []
    for verse_num in sorted(verse_map):
        text = verse_map[verse_num].strip()
        if not text:
            continue
        if include_numbers:
            lines.append(f"{verse_num} {text}")
        else:
            lines.append(text)
    return separator.join(lines)


def _resolve_range(data: dict[str, Any]) -> ScriptureRange | None:
    chapter = data.get("scripture_chapter")
    start = data.get("scripture_verse_start")
    end = data.get("scripture_verse_end")
    if chapter is not None and start is not None and end is not None:
        return ScriptureRange(
            book=None,
            chapter=int(chapter),
            start=int(start),
            end=int(end),
        )
    return parse_scripture_range(str(data.get("scripture", "")))


def _http_get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    raw = urllib.request.urlopen(request, timeout=20).read()
    for encoding in ("utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _clean_html_text(fragment: str) -> str:
    """Keep only scripture text; drop bskorea footnotes and variant notes."""
    text = _strip_bskorea_annotations(fragment)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    return _normalize_spaces(text)


def _strip_bskorea_annotations(fragment: str) -> str:
    """Remove popup footnotes and inline variant markers from bskorea HTML."""
    text = fragment
    text = re.sub(
        r"<div\b[^>]*\bclass\s*=\s*['\"]?D\d+['\"]?[^>]*>.*?</div>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"<a\b[^>]*\bclass\s*=\s*['\"]?comment['\"]?[^>]*>.*?</a>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return text


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
