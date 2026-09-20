"""Extract sermon part verse references and quotes from sermon PDF text."""

from __future__ import annotations

import re
from typing import Any

PART_OUTLINE_PAREN_PATTERN = re.compile(
    r"(\d)\.\s*([^(]+?)\(([^)]+)\)\s*\n\s*\(([^)]+)\)",
    re.MULTILINE,
)

PART_OUTLINE_EQUALS_PATTERN = re.compile(
    r"(?P<index>[1-3])\.\s*(?P<title>[^(]+?)\((?P<verse>[^)]+)\)\s*\n\s*=\s*"
    r"(?P<desc>.+?)(?=\n[1-3]\.\s|\n관찰|\n본문|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Numbered outline start: "1. title..." (may wrap onto later lines).
PART_OUTLINE_START_PATTERN = re.compile(r"(?m)^([1-3])\.\s*(.*)$")

# Opening paren whose content begins with a verse range (may continue as "절=desc").
PART_OUTLINE_VERSE_OPEN_PATTERN = re.compile(
    r"\((\s*\d+(?:\s*[-~]\s*\d+)?\s*절?)",
    re.DOTALL,
)

# Verse number/range at the start of a paren body (optional trailing "절").
_VERSE_HEAD_PATTERN = re.compile(
    r"^\s*(\d+(?:\s*[-~]\s*\d+)?)\s*절?\s*",
    re.DOTALL,
)

# Legacy exact "(verse)" matcher kept for older imports/tests.
PART_OUTLINE_VERSE_PATTERN = re.compile(
    r"\(\s*(\d+(?:\s*[-~]\s*\d+)?\s*절?)\s*\)",
    re.DOTALL,
)

# Backward-compatible alias used by older imports/tests.
PART_OUTLINE_PATTERN = PART_OUTLINE_PAREN_PATTERN

OUTLINE_STOP_MARKERS = (
    "관찰",
    "본문",
    "적용적해석",
    "대제",
)

BODY_QUOTE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?P<start>\d{1,2})(?:[-~](?P<end>\d{1,2}))?"
    r"\s*절?"
    r"\s*(?:\n\s*)?"
    r"=\s*"
    r'["“](?P<quote>.*?)["”]',
    re.DOTALL,
)

TRUNCATED_QUOTE_PATTERN = re.compile(r"^\.{2,}")
EN_CLAUSE_START_PATTERN = re.compile(
    r"\b(?:Now,\s*behold|I am|Then|And|Nevertheless|So now|Joshua|Therefore)\b",
    re.IGNORECASE,
)
EN_SENTENCE_BOUNDARY_PATTERN = re.compile(r'[.!?;]["\']?(?=\s|$)')


def _split_verse_and_desc(content: str) -> tuple[str, str]:
    """Split paren/body text into verse ref and optional description.

    Supports: '8절', '10-11절', '16~18', '19', '6-7절=설명'.
    """
    cleaned = content.strip()
    if not cleaned:
        return "", ""

    match = _VERSE_HEAD_PATTERN.match(cleaned)
    if not match:
        return "", ""

    verse_ref = re.sub(r"\s+", "", match.group(1))
    rest = cleaned[match.end() :].strip()
    if rest.startswith("="):
        return verse_ref, rest[1:].strip()
    return verse_ref, ""


def _parse_verse_ref(ref_text: str) -> tuple[int, int]:
    """Parse outline refs like '8절', '10-11절', '16~18절', or '6-7절=desc'."""
    verse_ref, _desc = _split_verse_and_desc(ref_text)
    cleaned = (verse_ref or ref_text).strip().replace("절", "").strip()
    # Drop any leftover description if split missed an odd form.
    for stopper in ("=", " "):
        if stopper in cleaned:
            cleaned = cleaned.split(stopper, 1)[0].strip()
    for separator in ("-", "~"):
        if separator in cleaned:
            start_text, end_text = cleaned.split(separator, 1)
            return int(start_text.strip()), int(end_text.strip())
    verse = int(cleaned)
    return verse, verse


def _normalize_outline_desc(desc: str) -> str:
    return re.sub(r"\s+", " ", desc.replace("\n", " ")).strip()


def _normalize_outline_title(title: str) -> str:
    return re.sub(r"\s+", "", title).strip()


def _normalize_outline_verse_ref(verse_ref: str) -> str:
    cleaned = re.sub(r"\s+", "", verse_ref.strip())
    if cleaned and not cleaned.endswith("절") and cleaned[-1].isdigit():
        cleaned = f"{cleaned}절"
    return cleaned


def _normalize_outline_fields(
    title: str,
    verse_raw: str,
    desc_raw: str = "",
) -> tuple[str, str, str] | None:
    """Normalize title/verse/desc; pull inline '=desc' out of the verse field."""
    verse_ref, inline_desc = _split_verse_and_desc(verse_raw)
    if not verse_ref:
        return None
    desc = inline_desc or desc_raw
    normalized_title = _normalize_outline_title(title)
    normalized_verse = _normalize_outline_verse_ref(verse_ref)
    if not normalized_title or not normalized_verse:
        return None
    return (
        normalized_title,
        normalized_verse,
        _normalize_outline_desc(desc),
    )


def _extract_outline_description(after_verse: str) -> str:
    """Extract description after a verse ref: '(desc)' or '= desc'."""
    paren_match = re.match(r"\s*\((.+?)\)", after_verse, re.DOTALL)
    if paren_match:
        return paren_match.group(1)

    # Truncated PDF text may omit the closing parenthesis.
    open_paren = re.match(r"\s*\((.+)", after_verse, re.DOTALL)
    if open_paren:
        return open_paren.group(1).split("\n", 1)[0]

    equals_match = re.match(r"\s*=\s*(.+)", after_verse, re.DOTALL)
    if equals_match:
        return equals_match.group(1).split("\n", 1)[0]

    return ""


def _extract_verse_paren_from_block(
    block: str,
) -> tuple[str, str, str, str] | None:
    """Find the first verse paren in a part block.

    Returns (title, verse_ref, inline_desc, text_after_paren).
    Handles '(13절)', '(16-17\\n절)', and '(6-7절=설명)'.
    """
    match = PART_OUTLINE_VERSE_OPEN_PATTERN.search(block)
    if not match:
        return None

    title = block[: match.start()]
    close = block.find(")", match.end())
    if close == -1:
        remainder = block[match.start() + 1 :]
        first_line, _, rest_lines = remainder.partition("\n")
        verse_ref, inline_desc = _split_verse_and_desc(first_line)
        if not verse_ref:
            return None
        return title, verse_ref, inline_desc, rest_lines

    inner = block[match.start() + 1 : close]
    verse_ref, inline_desc = _split_verse_and_desc(inner)
    if not verse_ref:
        return None
    return title, verse_ref, inline_desc, block[close + 1 :]


def _parse_outline_blocks(text: str) -> dict[int, tuple[str, str, str]]:
    """Parse outline parts even when titles/verse refs wrap across lines."""
    starts = list(PART_OUTLINE_START_PATTERN.finditer(text))
    parts: dict[int, tuple[str, str, str]] = {}

    for index, match in enumerate(starts):
        part_index = int(match.group(1))
        if part_index not in (1, 2, 3) or part_index in parts:
            continue

        if index + 1 < len(starts):
            block_end = starts[index + 1].start()
        else:
            block_end = len(text)
            remainder = text[match.end() :]
            for marker in OUTLINE_STOP_MARKERS:
                stop = re.search(rf"\n\s*{re.escape(marker)}", remainder)
                if stop:
                    block_end = min(block_end, match.end() + stop.start())

        block = text[match.start(2) : block_end]
        extracted = _extract_verse_paren_from_block(block)
        if not extracted:
            continue

        title, verse_ref, inline_desc, after = extracted
        desc = inline_desc or _extract_outline_description(after)
        normalized = _normalize_outline_fields(title, verse_ref, desc)
        if not normalized:
            continue

        parts[part_index] = normalized

    return parts


def parse_sermon_outline(text: str) -> list[tuple[int, str, str, str]]:
    """Return sermon outline parts as (index, title, verse_ref, description)."""
    parts: dict[int, tuple[str, str, str]] = {}

    for index_text, title, verse_ref, desc in PART_OUTLINE_PAREN_PATTERN.findall(text):
        part_index = int(index_text)
        if part_index not in (1, 2, 3):
            continue
        normalized = _normalize_outline_fields(title, verse_ref, desc)
        if normalized:
            parts[part_index] = normalized

    for match in PART_OUTLINE_EQUALS_PATTERN.finditer(text):
        part_index = int(match.group("index"))
        if part_index not in (1, 2, 3) or part_index in parts:
            continue
        normalized = _normalize_outline_fields(
            match.group("title"),
            match.group("verse"),
            match.group("desc"),
        )
        if normalized:
            parts[part_index] = normalized

    for part_index, payload in _parse_outline_blocks(text).items():
        if part_index not in parts:
            parts[part_index] = payload

    return [(index, *parts[index]) for index in sorted(parts) if index in parts]


def _ranges_overlap(
    outline_range: tuple[int, int],
    quote_range: tuple[int, int],
) -> bool:
    outline_start, outline_end = outline_range
    quote_start, quote_end = quote_range
    return quote_start <= outline_end and quote_end >= outline_start


def _match_quote_for_part(
    verse_range: tuple[int, int],
    quotes: dict[tuple[int, int], str],
    part_index: int,
    used_keys: set[tuple[int, int]],
) -> tuple[str, tuple[int, int] | None]:
    """Match a body quote to an outline part by exact, overlap, or order."""
    if verse_range in quotes and verse_range not in used_keys:
        return quotes[verse_range], verse_range

    overlapping = [
        key
        for key, quote in quotes.items()
        if key not in used_keys
        and quote.strip()
        and _ranges_overlap(verse_range, key)
    ]
    if len(overlapping) == 1:
        key = overlapping[0]
        return quotes[key], key
    if overlapping:
        overlapping.sort(key=lambda key: (abs(key[0] - verse_range[0]), key[0], key[1]))
        key = overlapping[0]
        return quotes[key], key

    ordered_keys = sorted(quotes.keys(), key=lambda key: (key[0], key[1]))
    unused = [key for key in ordered_keys if key not in used_keys and quotes[key].strip()]
    if part_index <= len(unused):
        key = unused[part_index - 1]
        return quotes[key], key

    return "", None


def _quote_is_truncated(quote: str) -> bool:
    stripped = quote.strip()
    if not stripped:
        return True
    if TRUNCATED_QUOTE_PATTERN.match(stripped):
        return True
    return stripped.startswith("…") or stripped.startswith("...")


def parse_sermon_part_verses(text: str) -> dict[int, dict[str, Any]]:
    """Return sermon part index -> verse range and optional KO quote from PDF body."""
    outline: dict[int, tuple[int, int]] = {}
    for part_index, _title, verse_ref, _desc in parse_sermon_outline(text):
        outline[part_index] = _parse_verse_ref(verse_ref)

    quotes: dict[tuple[int, int], str] = {}
    for match in BODY_QUOTE_PATTERN.finditer(text):
        start = int(match.group("start"))
        end = int(match.group("end") or start)
        quote = re.sub(r"\s+", " ", match.group("quote")).strip()
        if quote:
            quotes[(start, end)] = quote

    used_quote_keys: set[tuple[int, int]] = set()
    result: dict[int, dict[str, Any]] = {}
    for part_index in sorted(outline):
        verse_range = outline[part_index]
        start, end = verse_range
        ko_quote, matched_key = _match_quote_for_part(
            verse_range,
            quotes,
            part_index,
            used_quote_keys,
        )
        if matched_key is not None:
            used_quote_keys.add(matched_key)
            if matched_key != verse_range:
                start, end = matched_key

        result[part_index] = {
            "verse_start": start,
            "verse_end": end,
            "verse_ko_quote": ko_quote,
            "verse_ko_truncated": _quote_is_truncated(ko_quote),
        }
    return result


def format_part_verse_ref_ko(scripture: str, chapter: int, start: int, end: int) -> str:
    """Build a KO reference label like '14:8' or '14:10-11'."""
    if start == end:
        reference = f"{chapter}:{start}"
    else:
        reference = f"{chapter}:{start}-{end}"
    book_prefix = _extract_book_prefix(scripture)
    if book_prefix:
        return f"{book_prefix}{reference}"
    return reference


def format_part_verse_ref_en(book_name: str, chapter: int, start: int, end: int) -> str:
    """Build an EN reference label like 'Joshua 14:8'."""
    if start == end:
        reference = f"{chapter}:{start}"
    else:
        reference = f"{chapter}:{start}-{end}"
    return f"{book_name} {reference}"


def _extract_book_prefix(scripture: str) -> str:
    cleaned = scripture.strip()
    match = re.match(r"([가-힣A-Za-z]+)", cleaned)
    if not match:
        return ""
    return match.group(1)


def normalize_for_quote_match(text: str) -> str:
    """Collapse whitespace and ellipsis so PDF quotes can match bible text."""
    cleaned = re.sub(r"\.{2,}", "", text)
    cleaned = cleaned.replace("…", "")
    return re.sub(r"\s+", "", cleaned)


def find_quote_span_in_passage(quote: str, passage: str) -> tuple[int, int] | None:
    """Return normalized (start, length) of quote within passage."""
    normalized_quote = normalize_for_quote_match(quote.lstrip("."))
    normalized_passage = normalize_for_quote_match(passage)
    if not normalized_quote or not normalized_passage:
        return None

    index = normalized_passage.find(normalized_quote)
    if index >= 0:
        return index, len(normalized_quote)

    start_index = -1
    prefix_len = 0
    for length in range(len(normalized_quote), 0, -1):
        idx = normalized_passage.find(normalized_quote[:length])
        if idx >= 0:
            start_index = idx
            prefix_len = length
            break

    end_pos = -1
    min_suffix = min(3, len(normalized_quote))
    for length in range(len(normalized_quote), min_suffix - 1, -1):
        suffix = normalized_quote[-length:]
        idx = normalized_passage.find(suffix)
        if idx >= 0:
            end_pos = idx + length
            break

    if start_index >= 0 and end_pos > start_index:
        return start_index, end_pos - start_index
    if start_index >= 0:
        return start_index, prefix_len

    minimum_suffix = min(15, len(normalized_quote))
    for length in range(len(normalized_quote), minimum_suffix - 1, -1):
        suffix = normalized_quote[-length:]
        index = normalized_passage.find(suffix)
        if index >= 0:
            return index, length

    minimum_chunk = min(20, len(normalized_quote))
    for length in range(len(normalized_quote), minimum_chunk - 1, -1):
        for start in range(0, len(normalized_quote) - length + 1):
            chunk = normalized_quote[start : start + length]
            index = normalized_passage.find(chunk)
            if index >= 0:
                return index, length

    return None


def _build_passage_with_offsets(
    verse_map: dict[int, str],
) -> tuple[str, dict[int, tuple[int, int]]]:
    """Join verses and track normalized offsets for each verse number."""
    parts: list[str] = []
    offsets: dict[int, tuple[int, int]] = {}
    norm_pos = 0

    for verse_num in sorted(verse_map):
        if parts:
            norm_pos += 1
        verse_start = norm_pos
        norm_pos += len(normalize_for_quote_match(verse_map[verse_num]))
        offsets[verse_num] = (verse_start, norm_pos)
        parts.append(verse_map[verse_num])

    return " ".join(parts), offsets


def extract_passage_span(passage: str, norm_start: int, norm_len: int) -> str:
    """Map a normalized character span back to passage text with spacing."""
    collected: list[str] = []
    norm_index = 0
    span_end = norm_start + norm_len
    in_span = False

    for char in passage:
        if char.isspace():
            if in_span and norm_index < span_end:
                collected.append(" ")
            continue

        if norm_index >= span_end:
            break

        if norm_index >= norm_start:
            in_span = True
            collected.append(char)
        norm_index += 1

    return re.sub(r"\s+", " ", "".join(collected)).strip()


def extract_passage_suffix(passage: str, suffix_norm_len: int) -> str:
    """Return the trailing normalized-length span from passage."""
    total = len(normalize_for_quote_match(passage))
    if suffix_norm_len <= 0 or total <= 0:
        return ""
    norm_start = max(0, total - suffix_norm_len)
    return extract_passage_span(passage, norm_start, total - norm_start)


def align_passage_to_pdf_quote(pdf_quote: str, passage: str) -> str:
    """Trim passage text to the portion that matches a PDF quote."""
    if not pdf_quote.strip():
        return passage.strip()

    span = find_quote_span_in_passage(pdf_quote, passage)
    if span is None:
        return passage.strip()

    return extract_passage_span(passage, span[0], span[1])


def map_parallel_passage_span(source: str, target: str, norm_start: int, norm_len: int) -> str:
    """Map a normalized span from source passage onto a parallel target passage."""
    source_norm_len = len(normalize_for_quote_match(source))
    if source_norm_len == 0:
        return target.strip()

    start_ratio = norm_start / source_norm_len
    end_ratio = (norm_start + norm_len) / source_norm_len
    return _english_from_word_ratio(target, start_ratio, end_ratio)


def _token_index_for_ratio(token_count: int, ratio: float) -> int:
    if token_count <= 0:
        return 0
    if ratio >= 1.0:
        return token_count - 1
    return max(0, min(token_count - 1, round(token_count * ratio) - 1))


def _char_index_of_token(text: str, tokens: list[str], token_index: int) -> int:
    if not tokens:
        return 0
    token_index = max(0, min(len(tokens) - 1, token_index))
    target = tokens[token_index]
    position = 0
    for index, token in enumerate(tokens):
        found = text.find(token, position)
        if found < 0:
            continue
        if index == token_index:
            return found
        position = found + len(token)
    return 0


def _snap_en_start_to_clause(text: str, start_pos: int) -> int:
    prefix = text[:start_pos]
    boundary = max(prefix.rfind("."), prefix.rfind(";"), prefix.rfind(","))
    if boundary >= 0:
        return boundary + 1
    return start_pos


def _snap_en_end_to_boundary(text: str, end_pos: int) -> int:
    suffix = text[end_pos:]
    match = EN_SENTENCE_BOUNDARY_PATTERN.search(suffix)
    if match:
        return end_pos + match.end()
    comma = re.search(r',(?=\s|$)', suffix)
    if comma:
        return end_pos + comma.end()
    return end_pos


def _english_through_word_ratio(en_verse: str, word_ratio: float) -> str:
    """Take an EN prefix that corresponds to a KO prefix, ending at a sentence boundary."""
    tokens = en_verse.split()
    if not tokens:
        return ""
    if word_ratio >= 0.95:
        return en_verse.strip()

    anchor_index = _token_index_for_ratio(len(tokens), word_ratio)
    anchor_pos = _char_index_of_token(en_verse, tokens, anchor_index)
    anchor_end = anchor_pos + len(tokens[anchor_index])
    end_pos = _snap_en_end_to_boundary(en_verse, anchor_end)
    return en_verse[:end_pos].strip()


def _english_from_word_ratio(en_verse: str, start_ratio: float, end_ratio: float) -> str:
    """Take an EN span using word ratios and snap to readable clause boundaries."""
    tokens = en_verse.split()
    if not tokens:
        return ""

    if end_ratio >= 0.95:
        start_index = _token_index_for_ratio(len(tokens), start_ratio)
        start_pos = _snap_en_start_to_clause(
            en_verse,
            _char_index_of_token(en_verse, tokens, start_index),
        )
        return en_verse[start_pos:].strip()

    if start_ratio <= 0.05:
        return _english_through_word_ratio(en_verse, end_ratio)

    start_index = _token_index_for_ratio(len(tokens), start_ratio)
    end_index = max(start_index, _token_index_for_ratio(len(tokens), end_ratio))
    start_pos = _snap_en_start_to_clause(
        en_verse,
        _char_index_of_token(en_verse, tokens, start_index),
    )
    end_pos = _snap_en_end_to_boundary(
        en_verse,
        _char_index_of_token(en_verse, tokens, end_index) + len(tokens[end_index]),
    )
    if end_pos <= start_pos:
        return _english_through_word_ratio(en_verse, end_ratio)
    return en_verse[start_pos:end_pos].strip()


def _map_ko_overlap_to_en(
    ko_verse: str,
    en_verse: str,
    local_start: int,
    local_len: int,
) -> str:
    """Map a KO sub-span within one verse to the parallel EN text."""
    verse_norm = len(normalize_for_quote_match(ko_verse))
    if verse_norm <= 0 or not en_verse.strip():
        return en_verse.strip()

    overlap_ratio = local_len / verse_norm
    start_ratio = local_start / verse_norm
    end_ratio = start_ratio + overlap_ratio

    if overlap_ratio >= 0.85:
        return en_verse.strip()
    if local_start == 0:
        return _english_through_word_ratio(en_verse, end_ratio)
    if end_ratio >= 0.92:
        return _english_from_word_ratio(en_verse, start_ratio, 1.0)
    return _english_from_word_ratio(en_verse, start_ratio, end_ratio)


def _merge_pdf_word_variants(spaced_bible: str, pdf_quote: str) -> str:
    """Keep bible spacing while preserving PDF-only character variants (e.g. typos)."""
    bible_norm = normalize_for_quote_match(spaced_bible)
    pdf_norm = normalize_for_quote_match(pdf_quote)
    if bible_norm == pdf_norm:
        return spaced_bible
    if len(bible_norm) != len(pdf_norm):
        return spaced_bible

    pdf_chars = iter(pdf_norm)
    merged: list[str] = []
    for char in spaced_bible:
        if char.isspace():
            merged.append(char)
        else:
            merged.append(next(pdf_chars, char))
    return re.sub(r"\s+", " ", "".join(merged)).strip()


def restore_ko_quote_spacing(pdf_quote: str, bible_passage: str) -> str:
    """Restore spacing from bible text for any PDF quote shape."""
    pdf_clean = re.sub(r"\s+", " ", pdf_quote).strip()
    if not pdf_clean:
        return bible_passage.strip()

    span = find_quote_span_in_passage(pdf_clean, bible_passage)
    if span is None:
        return pdf_clean

    spaced = extract_passage_span(bible_passage, span[0], span[1])
    if not spaced:
        return pdf_clean
    return _merge_pdf_word_variants(spaced, pdf_clean)


def build_sermon_part_ko_en(
    pdf_quote: str,
    ko_map: dict[int, str],
    en_map: dict[int, str],
    *,
    truncated: bool,
) -> tuple[str, str]:
    """Build KO/EN text for a sermon part from PDF quote and bible verses."""
    ko_passage, _offsets = _build_passage_with_offsets(ko_map)

    if not pdf_quote.strip():
        en_passage, _ = _build_passage_with_offsets(en_map)
        return ko_passage.strip(), en_passage.strip()

    if truncated:
        ko_text = restore_ko_quote_spacing(pdf_quote, ko_passage)
        _ko_aligned, en_text = align_ko_and_en_to_pdf_quote(pdf_quote, ko_map, en_map)
        return ko_text, en_text

    ko_text = restore_ko_quote_spacing(pdf_quote, ko_passage)
    _ko_aligned, en_text = align_ko_and_en_to_pdf_quote(pdf_quote, ko_map, en_map)
    return ko_text, en_text


def align_ko_and_en_to_pdf_quote(
    pdf_quote: str,
    ko_map: dict[int, str],
    en_map: dict[int, str],
) -> tuple[str, str]:
    """Align KO/EN bible text to the PDF quote, trimming both to the same span."""
    ko_passage, ko_offsets = _build_passage_with_offsets(ko_map)
    en_passage, _en_offsets = _build_passage_with_offsets(en_map)

    if not pdf_quote.strip():
        return ko_passage.strip(), en_passage.strip()

    span = find_quote_span_in_passage(pdf_quote, ko_passage)
    ko_text = restore_ko_quote_spacing(pdf_quote, ko_passage)
    if span is None:
        return ko_text, en_passage.strip()

    norm_start, norm_len = span
    norm_end = norm_start + norm_len

    en_parts: list[str] = []
    for verse_num in sorted(ko_map):
        verse_start, verse_end = ko_offsets[verse_num]
        if verse_end <= norm_start or verse_start >= norm_end:
            continue

        ko_verse = ko_map[verse_num]
        en_verse = en_map.get(verse_num, "")
        fully_inside = verse_start >= norm_start and verse_end <= norm_end
        if fully_inside:
            en_parts.append(en_verse)
            continue

        overlap_start = max(norm_start, verse_start)
        overlap_end = min(norm_end, verse_end)
        local_start = overlap_start - verse_start
        local_len = overlap_end - overlap_start
        verse_norm = len(normalize_for_quote_match(ko_verse))
        continues_to_next = overlap_end == verse_end and norm_end > verse_end

        if verse_norm > 0 and local_len / verse_norm >= 0.85:
            en_parts.append(en_verse)
            continue

        if continues_to_next:
            en_parts.append(en_verse)
            continue

        en_parts.append(_map_ko_overlap_to_en(ko_verse, en_verse, local_start, local_len))

    en_text = " ".join(part for part in en_parts if part).strip()
    en_text = _clean_en_clause_start(en_text)
    return ko_text, en_text or _build_passage_with_offsets(en_map)[0].strip()


def _clean_en_clause_start(text: str) -> str:
    """Drop a leading broken English fragment before a clause boundary."""
    stripped = text.strip()
    if not stripped:
        return stripped

    match = EN_CLAUSE_START_PATTERN.search(stripped)
    if match and match.start() > 0:
        prefix = stripped[: match.start()]
        if prefix and prefix.strip() and prefix.lstrip()[0].islower():
            return stripped[match.start() :].strip()
    return stripped
