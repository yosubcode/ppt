"""Auto-translate Korean worship slide text to English."""

from __future__ import annotations

import os
import re
from typing import Any

from deep_translator import GoogleTranslator

from korean_text import strip_english_verse_reference

HANGUL_PATTERN = re.compile(r"[\uAC00-\uD7A3]")

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


def translate_ko_to_en(text: str) -> str:
    """Translate Korean text to English."""
    cleaned = text.strip()
    if not cleaned:
        return ""

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        translated = _translate_with_openai(cleaned, api_key)
    else:
        translated = GoogleTranslator(source="ko", target="en").translate(cleaned)

    return capitalize_english_text(translated)


def translate_responsive_lines_esv(lines: list[str]) -> list[str]:
    """Translate responsive reading lines to ESV-style English, one line per slide."""
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    if not cleaned_lines:
        return []

    api_key = os.getenv("OPENAI_API_KEY")
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
    for line in cleaned_lines:
        translated_lines.append(
            capitalize_english_text(
                GoogleTranslator(source="ko", target="en").translate(line)
            )
        )
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
