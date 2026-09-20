"""Auto-translate Korean worship slide text to English."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from deep_translator import GoogleTranslator, MyMemoryTranslator

from korean_text import strip_english_verse_reference

HANGUL_PATTERN = re.compile(r"[\uAC00-\uD7A3]")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
GOOGLE_GTX_URL = "https://translate.googleapis.com/translate_a/single"
GOOGLE_TRANSLATE_RETRIES = 4
GOOGLE_RETRY_BASE_SECONDS = 1.0
GOOGLE_RATE_LIMIT_SECONDS = 3.0
RESPONSIVE_LINE_GAP_SECONDS = 0.35

# Korean source field -> English target field
SIMPLE_TRANSLATION_PAIRS: list[tuple[str, str]] = [
    ("sermon_title", "sermon_title_eng"),
]

# Korean part fields -> English field (desc included when present)
PART_TRANSLATION_GROUPS: list[tuple[str, str, str]] = [
    ("sermon_part1", "sermon_part1_desc", "sermon_part1_eng"),
    ("sermon_part2", "sermon_part2_desc", "sermon_part2_eng"),
    ("sermon_part3", "sermon_part3_desc", "sermon_part3_eng"),
]


def contains_korean(text: str) -> bool:
    return bool(HANGUL_PATTERN.search(text))


def _set_english_field(
    updated: dict[str, Any],
    target_field: str,
    translated_fields: list[str],
    translated_text: str,
) -> None:
    updated[target_field] = translated_text
    translated_fields.append(target_field)


def _capitalize_first_alpha(text: str) -> str:
    """Uppercase the first alphabetic character in text."""
    chars = list(text)
    for index, char in enumerate(chars):
        if char.isalpha():
            chars[index] = char.upper()
            break
    return "".join(chars)


def capitalize_english_text(text: str) -> str:
    """Capitalize the first letter of each line and parenthetical line."""
    lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.lstrip()
        if not stripped:
            lines.append(line)
            continue

        leading_spaces = line[: len(line) - len(stripped)]
        if stripped.startswith("("):
            inner = stripped[1:]
            closing = ")" if inner.endswith(")") else ""
            body = inner[:-1] if closing else inner
            capitalized = f"({_capitalize_first_alpha(body)}{closing}"
            lines.append(leading_spaces + capitalized)
        else:
            lines.append(leading_spaces + _capitalize_first_alpha(stripped))

    return "\n".join(lines)


def _translate_with_openai(text: str, api_key: str, *, system_prompt: str | None = None) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        input=[
            {
                "role": "system",
                "content": system_prompt
                or (
                    "Translate Korean church worship slide text into natural English. "
                    "Keep sermon titles concise. Capitalize the first letter. "
                    "Return translation only."
                ),
            },
            {"role": "user", "content": text},
        ],
    )
    return response.output_text.strip()


def _translate_with_google_gtx(text: str) -> str:
    """Translate via Google's public gtx JSON endpoint (more stable than HTML scrape)."""
    query = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "ko",
            "tl": "en",
            "dt": "t",
            "q": text,
        }
    )
    request = urllib.request.Request(
        f"{GOOGLE_GTX_URL}?{query}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Google gtx HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Google gtx network error: {error.reason}") from error

    chunks = payload[0] if isinstance(payload, list) and payload else []
    translated = "".join(
        str(part[0])
        for part in chunks
        if isinstance(part, list) and part and part[0]
    ).strip()
    if not translated:
        raise RuntimeError("Google gtx returned empty translation")
    return translated


def _translate_with_google_scrape(text: str) -> str:
    """Fallback to deep_translator HTML scrape."""
    translated = GoogleTranslator(source="ko", target="en").translate(text)
    if translated is None or not str(translated).strip():
        raise RuntimeError("Google scrape returned empty translation")
    return str(translated).strip()


def _translate_with_mymemory(text: str) -> str:
    """Fallback free translator when Google rate-limits."""
    translated = MyMemoryTranslator(source="ko-KR", target="en-GB").translate(text)
    if translated is None or not str(translated).strip():
        raise RuntimeError("MyMemory returned empty translation")
    return str(translated).strip()


def _is_rate_limited(error: Exception) -> bool:
    name = type(error).__name__.lower()
    message = str(error).lower()
    return (
        "429" in message
        or "too many" in message
        or "ratelimit" in name
        or "toomanyrequests" in name
    )


def _translate_with_google(text: str) -> str:
    """Translate with retries across Google/MyMemory. Raises if all attempts fail."""
    backends: tuple[Callable[[str], str], ...] = (
        _translate_with_google_gtx,
        _translate_with_google_scrape,
        _translate_with_mymemory,
    )
    last_error: Exception | None = None

    for attempt in range(GOOGLE_TRANSLATE_RETRIES):
        for backend in backends:
            try:
                return backend(text)
            except Exception as error:
                last_error = error
                if _is_rate_limited(error):
                    time.sleep(GOOGLE_RATE_LIMIT_SECONDS * (attempt + 1))
        time.sleep(GOOGLE_RETRY_BASE_SECONDS * (attempt + 1))

    raise RuntimeError(
        f"Translation failed after {GOOGLE_TRANSLATE_RETRIES} retries: {last_error}"
    ) from last_error


def translate_ko_to_en(text: str) -> str:
    """Translate Korean text to English."""
    cleaned = text.strip()
    if not cleaned:
        return ""

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        translated = _translate_with_openai(cleaned, api_key)
    else:
        translated = _translate_with_google(cleaned)

    return capitalize_english_text(translated)


def translate_responsive_lines_esv(lines: list[str]) -> list[str]:
    """Translate responsive reading lines to ESV-style English, one line per slide."""
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    if not cleaned_lines:
        return []

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        numbered = "\n".join(f"{index + 1}. {line}" for index, line in enumerate(cleaned_lines))
        translated_block = _translate_with_openai(
            numbered,
            api_key,
            system_prompt=(
                "Translate each numbered Korean responsive reading line into English "
                "using ESV (English Standard Version) biblical wording whenever the "
                "source text is Scripture. Keep the same numbering and one English line "
                "per numbered item. Return translation only."
            ),
        )
        return _parse_numbered_translation_block(translated_block, len(cleaned_lines))

    translated_lines: list[str] = []
    for index, line in enumerate(cleaned_lines):
        if index:
            # Gap reduces Google 429 failures on long responsive readings.
            time.sleep(RESPONSIVE_LINE_GAP_SECONDS)
        translated_lines.append(capitalize_english_text(_translate_with_google(line)))
    return translated_lines


def _parse_numbered_translation_block(text: str, expected_count: int) -> list[str]:
    matches = re.findall(r"^\s*\d+\.\s*(.+)$", text, flags=re.MULTILINE)
    if len(matches) >= expected_count:
        return [capitalize_english_text(match.strip()) for match in matches[:expected_count]]

    fallback_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(fallback_lines) >= expected_count:
        return [capitalize_english_text(line) for line in fallback_lines[:expected_count]]

    while len(fallback_lines) < expected_count:
        fallback_lines.append("")
    return [capitalize_english_text(line) for line in fallback_lines[:expected_count]]


def _build_part_english(part: str, desc: str | None) -> str:
    translated_part = strip_english_verse_reference(translate_ko_to_en(part))
    if desc and str(desc).strip():
        translated_desc = strip_english_verse_reference(translate_ko_to_en(str(desc)))
        return f"{translated_part}\n({translated_desc})"
    return translated_part


def fill_english_fields(
    data: dict[str, Any],
    *,
    enabled: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    """
    Fill English fields from Korean source fields.

    Returns updated data and a list of fields that were translated.
    """
    if not enabled:
        return data, []

    updated = dict(data)
    translated_fields: list[str] = []

    for source_field, target_field in SIMPLE_TRANSLATION_PAIRS:
        source_value = updated.get(source_field)
        if not source_value or not str(source_value).strip():
            continue

        source_text = str(source_value).strip()
        if contains_korean(source_text):
            _set_english_field(
                updated,
                target_field,
                translated_fields,
                translate_ko_to_en(source_text),
            )
        elif not updated.get(target_field):
            updated[target_field] = source_text

    for part_field, desc_field, eng_field in PART_TRANSLATION_GROUPS:
        part_value = updated.get(part_field)
        if not part_value or not str(part_value).strip():
            continue

        part_text = str(part_value).strip()
        desc_value = updated.get(desc_field)
        desc_text = str(desc_value).strip() if desc_value else ""

        if contains_korean(part_text) or (desc_text and contains_korean(desc_text)):
            _set_english_field(
                updated,
                eng_field,
                translated_fields,
                _build_part_english(part_text, desc_text or None),
            )
        elif not updated.get(eng_field):
            updated[eng_field] = (
                f"{part_text}\n({desc_text})" if desc_text else part_text
            )

    return updated, translated_fields
