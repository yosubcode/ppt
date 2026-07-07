"""Parse scripture references and verse text for slide generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SCRIPTURE_RANGE_PATTERN = re.compile(
    r"(?:(?P<book>[가-힣A-Za-z]+))?"
    r"(?P<chapter>\d+)\s*:\s*(?P<start>\d+)"
    r"(?:\s*-\s*(?P<end>\d+))?",
)

# Matches ESV-style inline verse numbers: "6 Then...", "...me. 7 I was..."
VERSE_MARKER_PATTERN = re.compile(
    r"(?:^|[\s\n])"
    r"(?P<num>\d{1,3})\s+"
    r"(?:(?P<fn>[a-z]))?"
    r"(?=[A-Z\"'])",
    re.MULTILINE,
)

VERSE_PREFIX_PATTERN = re.compile(
    r"^\s*(?:\[(?P<bracket>\d+)\]"
    r"|(?:(?P<chapter>\d+):(?P<colon_verse>\d+))"
    r"|(?P<verse_only>\d+)(?:\s*절)?)"
    r"\s*[\.\):]?\s*(?:[a-z])?"
    r"(?P<rest>.*)$",
    re.DOTALL,
)

ESV_BRACKET_MARKER_PATTERN = re.compile(r"\[(\d+)\]")


@dataclass
class ScriptureRange:
    book: str | None
    chapter: int
    start: int
    end: int

    @property
    def count(self) -> int:
        return self.end - self.start + 1

    def verse_numbers(self) -> list[int]:
        return list(range(self.start, self.end + 1))

    def verse_ref(self, verse: int) -> str:
        return f"{self.chapter}:{verse}"


def parse_scripture_range(scripture: str) -> ScriptureRange | None:
    """Parse strings like '수14:6-15' or '14:6-15'."""
    cleaned = scripture.strip()
    if not cleaned:
        return None

    match = SCRIPTURE_RANGE_PATTERN.search(cleaned)
    if not match:
        return None

    chapter = int(match.group("chapter"))
    start = int(match.group("start"))
    end = int(match.group("end") or start)
    if end < start:
        start, end = end, start

    book = match.group("book")
    return ScriptureRange(book=book, chapter=chapter, start=start, end=end)


def apply_scripture_range_to_data(data: dict[str, Any]) -> dict[str, Any]:
    """Add chapter and verse range fields from the scripture reference string."""
    scripture = str(data.get("scripture", "")).strip()
    if not scripture:
        return data

    parsed = parse_scripture_range(scripture)
    if not parsed:
        return data

    updated = dict(data)
    updated["scripture_chapter"] = parsed.chapter
    updated["scripture_verse_start"] = parsed.start
    updated["scripture_verse_end"] = parsed.end
    return updated


def split_bulk_verse_text(
    text: str,
    scripture_range: ScriptureRange | None = None,
) -> dict[int, str]:
    """Split bulk pasted KO or EN text into verse-number -> text mapping."""
    cleaned = text.strip()
    if not cleaned:
        return {}

    numbered = _split_esv_bracket_verse_text(cleaned, scripture_range)
    if numbered and _numbered_split_looks_complete(numbered, scripture_range):
        return numbered

    numbered = _split_numbered_verse_text(cleaned, scripture_range)
    if numbered and _numbered_split_looks_complete(numbered, scripture_range):
        return numbered

    return _split_paragraph_verse_text(cleaned, scripture_range)


def _numbered_split_looks_complete(
    numbered: dict[int, str],
    scripture_range: ScriptureRange | None,
) -> bool:
    if not numbered:
        return False
    if scripture_range is None:
        return True
    expected = scripture_range.verse_numbers()
    return sorted(numbered.keys()) == expected


def _split_paragraph_verse_text(
    text: str,
    scripture_range: ScriptureRange | None,
) -> dict[int, str]:
    """Split by blank lines or one line per verse (typical Korean paste)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    parts = [part.strip() for part in re.split(r"\n\s*\n+", text.strip()) if part.strip()]
    expected_count = scripture_range.count if scripture_range else None

    # Prefer one line per verse when line count matches the scripture range.
    if expected_count and len(lines) == expected_count:
        return _map_parts_to_range(lines, scripture_range)

    if expected_count and len(parts) == expected_count:
        return _map_parts_to_range(parts, scripture_range)

    if len(lines) > 1 and (expected_count is None or len(lines) <= expected_count):
        return _map_parts_to_range(lines, scripture_range)

    if parts:
        return _map_parts_to_range(parts, scripture_range)

    if lines:
        return _map_parts_to_range(lines, scripture_range)

    return {}


def _map_parts_to_range(
    parts: list[str],
    scripture_range: ScriptureRange | None,
) -> dict[int, str]:
    if scripture_range is None:
        return {index + 1: part for index, part in enumerate(parts)}

    result: dict[int, str] = {}
    for index, verse_num in enumerate(scripture_range.verse_numbers()):
        if index >= len(parts):
            break
        result[verse_num] = parts[index]
    return result


def _split_esv_bracket_verse_text(
    text: str,
    scripture_range: ScriptureRange | None = None,
) -> dict[int, str]:
    """Split ESV API text where verse numbers appear as inline [6], [7], markers."""
    if not ESV_BRACKET_MARKER_PATTERN.search(text):
        return {}

    marker_matches = list(ESV_BRACKET_MARKER_PATTERN.finditer(text))
    if not marker_matches:
        return {}

    raw: dict[int, str] = {}
    for index, match in enumerate(marker_matches):
        verse_num = int(match.group(1))
        text_start = match.end()
        text_end = marker_matches[index + 1].start() if index + 1 < len(marker_matches) else len(text)
        raw[verse_num] = text[text_start:text_end].strip()

    if scripture_range is None:
        return {num: _normalize_verse_text(body) for num, body in raw.items()}

    return _expand_esv_bracket_gaps(raw, scripture_range)


def _expand_esv_bracket_gaps(
    raw: dict[int, str],
    scripture_range: ScriptureRange,
) -> dict[int, str]:
    expected = scripture_range.verse_numbers()
    marker_nums = sorted(num for num in raw if num in expected)
    if not marker_nums:
        return {}

    result: dict[int, str] = {}
    for index, start_num in enumerate(marker_nums):
        chunk = raw[start_num]
        next_num = marker_nums[index + 1] if index + 1 < len(marker_nums) else expected[-1] + 1
        span = next_num - start_num
        if span <= 1:
            result[start_num] = _normalize_verse_text(chunk)
            continue
        for offset, part in enumerate(_split_esv_span(chunk, span)):
            verse_num = start_num + offset
            if verse_num in expected:
                result[verse_num] = _normalize_verse_text(part)

    return {num: result[num] for num in expected if num in result}


def _split_esv_span(chunk: str, span: int) -> list[str]:
    cleaned = chunk.strip()
    if span <= 1:
        return [cleaned]

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", cleaned) if part.strip()]
    if len(paragraphs) == span:
        return paragraphs
    if len(paragraphs) > span:
        head = paragraphs[: span - 1]
        tail = " ".join(paragraphs[span - 1 :])
        return head + [tail]

    parts = re.split(r"\n\s*\n+", cleaned, maxsplit=span - 1)
    if len(parts) == span:
        return [_normalize_verse_text(part) for part in parts]

    return [cleaned] + [""] * (span - 1)


def _normalize_verse_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_numbered_verse_text(
    text: str,
    scripture_range: ScriptureRange | None = None,
) -> dict[int, str]:
    markers = _find_verse_markers(text, scripture_range)
    if not markers:
        return {}

    result: dict[int, str] = {}
    for index, (verse_num, start_pos) in enumerate(markers):
        end_pos = markers[index + 1][1] if index + 1 < len(markers) else len(text)
        block = text[start_pos:end_pos].strip()
        result[verse_num] = _strip_verse_prefix(block)
    return result


def _find_verse_markers(
    text: str,
    scripture_range: ScriptureRange | None,
) -> list[tuple[int, int]]:
    expected_nums = scripture_range.verse_numbers() if scripture_range else None
    expected_set = set(expected_nums) if expected_nums else None

    raw: list[tuple[int, int]] = []
    for match in VERSE_MARKER_PATTERN.finditer(text):
        verse_num = int(match.group("num"))
        if expected_set is not None and verse_num not in expected_set:
            continue
        raw.append((verse_num, match.start("num")))

    if not raw:
        return []

    filtered: list[tuple[int, int]] = []
    for verse_num, pos in raw:
        if filtered and verse_num <= filtered[-1][0]:
            continue
        filtered.append((verse_num, pos))

    if not expected_nums:
        return filtered

    aligned: list[tuple[int, int]] = []
    marker_index = 0
    for expected in expected_nums:
        while marker_index < len(filtered) and filtered[marker_index][0] < expected:
            marker_index += 1
        if marker_index < len(filtered) and filtered[marker_index][0] == expected:
            aligned.append(filtered[marker_index])
            marker_index += 1

    if len(aligned) == len(expected_nums):
        return aligned
    return filtered


def _strip_verse_prefix(block: str) -> str:
    first_line = block.splitlines()[0] if block else block
    line_match = VERSE_PREFIX_PATTERN.match(first_line)
    body_lines: list[str] = []
    if line_match and line_match.group("rest"):
        body_lines.append(line_match.group("rest").strip())
    body_lines.extend(line.strip() for line in block.splitlines()[1:] if line.strip())
    return "\n".join(body_lines).strip()


def strip_english_verse_number(text: str) -> str:
    """Remove a leading verse number from English scripture text for slide display."""
    cleaned = text.strip()
    if not cleaned:
        return ""
    stripped = _strip_verse_prefix(cleaned)
    return stripped if stripped else cleaned


def join_verse_texts(verses: list[dict[str, Any]], field: str) -> str:
    """Rebuild bulk paste text from structured verse entries."""
    blocks: list[str] = []
    for item in sorted(verses, key=lambda entry: int(entry.get("verse", 0))):
        value = str(item.get(field, "")).strip()
        if value:
            blocks.append(value)
    return "\n\n".join(blocks)


def build_scripture_verses(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build ordered verse entries for slide insertion."""
    if isinstance(data.get("scripture_verses"), list) and not (
        data.get("scripture_ko_text") or data.get("scripture_en_text")
    ):
        verses = []
        for item in data["scripture_verses"]:
            if not isinstance(item, dict):
                continue
            verse_num = int(item.get("verse", 0))
            if verse_num <= 0:
                continue
            verses.append(
                {
                    "verse": verse_num,
                    "ref": str(item.get("ref") or "").strip()
                    or _default_ref(data, verse_num),
                    "ko": str(item.get("ko", "")).strip(),
                    "en": strip_english_verse_number(str(item.get("en", ""))),
                }
            )
        return sorted(verses, key=lambda item: item["verse"])

    parsed = _resolve_scripture_range(data)
    if not parsed:
        return []

    ko_text = str(data.get("scripture_ko_text", "")).strip()
    en_text = str(data.get("scripture_en_text", "")).strip()
    ko_map = split_bulk_verse_text(ko_text, parsed)
    en_map = split_bulk_verse_text(en_text, parsed)

    verses: list[dict[str, Any]] = []
    for verse_num in parsed.verse_numbers():
        verses.append(
            {
                "verse": verse_num,
                "ref": parsed.verse_ref(verse_num),
                "ko": ko_map.get(verse_num, ""),
                "en": strip_english_verse_number(en_map.get(verse_num, "")),
            }
        )
    return verses


def verses_ready_for_insert(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return verse entries that have at least Korean or English text."""
    return [
        verse
        for verse in build_scripture_verses(data)
        if verse.get("ko") or verse.get("en")
    ]


def _resolve_scripture_range(data: dict[str, Any]) -> ScriptureRange | None:
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


def _default_ref(data: dict[str, Any], verse_num: int, *, chapter: int | None = None) -> str:
    chapter_value = chapter or data.get("scripture_chapter")
    if chapter_value is None:
        parsed = parse_scripture_range(str(data.get("scripture", "")))
        if parsed:
            chapter_value = parsed.chapter
    if chapter_value is None:
        return str(verse_num)
    return f"{chapter_value}:{verse_num}"
