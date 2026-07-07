"""Apply sermon part verse text with the same COM word-wrap handling as scripture slides."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripture_merger import _replace_token_in_shape

SERMON_VERSE_TOKEN_FIELDS: tuple[tuple[str, str], ...] = (
    ("{{VERSE_KO1}}", "verse_ko1"),
    ("{{VERSE_EN1}}", "verse_en1"),
    ("{{VERSE_KO2}}", "verse_ko2"),
    ("{{VERSE_EN2}}", "verse_en2"),
    ("{{VERSE_KO3}}", "verse_ko3"),
    ("{{VERSE_EN3}}", "verse_en3"),
)


def _iter_text_shapes(presentation):
    for slide_index in range(1, presentation.Slides.Count + 1):
        slide = presentation.Slides(slide_index)
        for shape_index in range(1, slide.Shapes.Count + 1):
            shape = slide.Shapes(shape_index)
            if shape.HasTextFrame and shape.TextFrame.HasText:
                yield shape


def _fill_sermon_verse_tokens(presentation, data: dict[str, Any]) -> dict[str, int]:
    stats = {"filled": 0, "missing": 0}
    for token, field in SERMON_VERSE_TOKEN_FIELDS:
        value = str(data.get(field, "")).strip()
        if not value:
            continue

        filled = False
        for shape in _iter_text_shapes(presentation):
            if token not in shape.TextFrame.TextRange.Text:
                continue
            _replace_token_in_shape(
                shape,
                token,
                value,
                prevent_word_splits=True,
            )
            filled = True
            stats["filled"] += 1
            break

        if not filled:
            stats["missing"] += 1

    return stats


def apply_sermon_part_verses(
    presentation_path: str | Path,
    data: dict[str, Any],
    *,
    presentation: Any | None = None,
) -> dict[str, int] | None:
    """Replace sermon part KO/EN placeholders using COM word-split prevention."""
    has_content = any(
        str(data.get(field, "")).strip()
        for _token, field in SERMON_VERSE_TOKEN_FIELDS
    )
    if not has_content:
        return None

    if presentation is not None:
        return _fill_sermon_verse_tokens(presentation, data)

    from ppt_com_session import powerpoint_edit_session

    with powerpoint_edit_session(presentation_path) as presentation_obj:
        return _fill_sermon_verse_tokens(presentation_obj, data)
