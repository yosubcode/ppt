"""Insert responsive reading slides using the RES template slide."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ppt_com_text import replace_token_in_shape
from responsive_parser import responsive_lines_ready_for_insert
from scripture_merger import (
    _get_slide_text,
    _layout_ko_en_shapes,
    _prevent_mid_word_line_breaks,
)

TOKEN_KO = "{{RES_KO}}"
TOKEN_EN = "{{RES_EN}}"
TOKEN_KO_LAST = "{{RES_KO_LAST}}"
TOKEN_EN_LAST = "{{RES_EN_LAST}}"

RESPONSIVE_SECTION_END_MARKERS = (
    "MEDITATIONALPRAYER",
    "묵상기도",
    "[기도문]",
    "[ALTOGETHER]",
    "대표기도",
    "{{PRAYER}}",
    "APOSTLESCREED",
    "사도신경",
)


def _normalize_marker(text: str) -> str:
    return re.sub(r"\s+", "", text).upper()


def _is_responsive_section_end(text: str) -> bool:
    normalized = _normalize_marker(text)
    return any(marker in normalized for marker in RESPONSIVE_SECTION_END_MARKERS)


def _slide_has_regular_template(text: str) -> bool:
    return TOKEN_KO in text and TOKEN_KO_LAST not in text


def _slide_has_last_template(text: str) -> bool:
    return TOKEN_KO_LAST in text


def _find_regular_template_index(presentation) -> int | None:
    for slide_index in range(1, presentation.Slides.Count + 1):
        slide_text = _get_slide_text(presentation.Slides(slide_index))
        if _slide_has_regular_template(slide_text):
            return slide_index
    return None


def _find_last_template_index(presentation) -> int | None:
    for slide_index in range(1, presentation.Slides.Count + 1):
        slide_text = _get_slide_text(presentation.Slides(slide_index))
        if _slide_has_last_template(slide_text):
            return slide_index
    return None


def _delete_extra_responsive_slides(
    presentation,
    regular_index: int,
    last_index: int,
) -> int:
    """Remove placeholder slides after the last template until the next section."""
    deleted = 0
    while last_index + 1 <= presentation.Slides.Count:
        next_slide = presentation.Slides(last_index + 1)
        next_text = _get_slide_text(next_slide)
        if _is_responsive_section_end(next_text):
            break
        if _slide_has_last_template(next_text) or _slide_has_regular_template(next_text):
            break
        next_slide.Delete()
        deleted += 1
    return deleted


def _find_responsive_shapes(slide, *, last: bool = False) -> dict[str, Any]:
    ko_token = TOKEN_KO_LAST if last else TOKEN_KO
    en_token = TOKEN_EN_LAST if last else TOKEN_EN
    other_ko_token = TOKEN_KO if last else TOKEN_KO_LAST

    shapes: dict[str, Any] = {}
    for shape_index in range(1, slide.Shapes.Count + 1):
        shape = slide.Shapes(shape_index)
        if not shape.HasTextFrame:
            continue
        text = shape.TextFrame.TextRange.Text
        has_ko = ko_token in text
        has_en = en_token in text
        if not last:
            has_ko = has_ko and other_ko_token not in text
        if has_ko and has_en:
            shapes["combined"] = shape
        elif has_ko:
            shapes["ko"] = shape
        elif has_en:
            shapes["en"] = shape
    return shapes


def _prevent_word_splits_in_shape(shape) -> None:
    if not shape.HasTextFrame:
        return

    text_frame = shape.TextFrame
    text_frame.WordWrap = True
    text_range = text_frame.TextRange
    try:
        paragraph_count = int(text_range.Paragraphs().Count)
    except Exception:
        paragraph_count = 0

    if paragraph_count <= 1:
        _prevent_mid_word_line_breaks(text_range)
        return

    for paragraph_index in range(1, paragraph_count + 1):
        paragraph = text_range.Paragraphs(paragraph_index)
        if str(paragraph.Text).strip():
            _prevent_mid_word_line_breaks(paragraph)


def _apply_combined_responsive_shape(shape, ko: str, en: str) -> None:
    """Replace KO/EN tokens in place so each paragraph keeps its template font."""
    replace_token_in_shape(shape, TOKEN_KO, ko)
    replace_token_in_shape(shape, TOKEN_EN, en)


def _apply_combined_last_shape(shape, ko: str, en: str) -> None:
    """Replace LAST tokens in place while keeping congregational response layout."""
    replace_token_in_shape(shape, TOKEN_KO_LAST, ko)
    replace_token_in_shape(shape, TOKEN_EN_LAST, en)


def _fill_responsive_slide(slide, line: dict[str, str], *, last: bool = False) -> None:
    shapes = _find_responsive_shapes(slide, last=last)
    ko = str(line.get("ko", ""))
    en = str(line.get("en", ""))

    if "ko" in shapes and "en" in shapes:
        if last:
            replace_token_in_shape(shapes["ko"], TOKEN_KO_LAST, ko)
            replace_token_in_shape(shapes["en"], TOKEN_EN_LAST, en)
        else:
            replace_token_in_shape(shapes["ko"], TOKEN_KO, ko)
            replace_token_in_shape(shapes["en"], TOKEN_EN, en)
        _prevent_word_splits_in_shape(shapes["ko"])
        _prevent_word_splits_in_shape(shapes["en"])
        if not last:
            _layout_ko_en_shapes(shapes["ko"], shapes["en"])
        return

    if "combined" in shapes:
        if last:
            _apply_combined_last_shape(shapes["combined"], ko, en)
        else:
            _apply_combined_responsive_shape(shapes["combined"], ko, en)
        _prevent_word_splits_in_shape(shapes["combined"])
        return

    if "ko" in shapes:
        token = TOKEN_KO_LAST if last else TOKEN_KO
        replace_token_in_shape(shapes["ko"], token, ko)
        _prevent_word_splits_in_shape(shapes["ko"])
    elif "en" in shapes:
        token = TOKEN_EN_LAST if last else TOKEN_EN
        replace_token_in_shape(shapes["en"], token, en)
        _prevent_word_splits_in_shape(shapes["en"])


def insert_responsive_reading(
    presentation_path: str | Path,
    data: dict[str, Any],
    *,
    translate: bool = True,
    presentation: Any | None = None,
) -> dict[str, int | str] | None:
    """Duplicate regular responsive slides and fill the last line on the LAST template."""
    lines = responsive_lines_ready_for_insert(data, translate=translate)
    if not lines:
        return None

    def _insert(presentation_obj) -> dict[str, int | str]:
        regular_index = _find_regular_template_index(presentation_obj)
        last_index = _find_last_template_index(presentation_obj)
        if regular_index is None:
            raise RuntimeError(
                "Responsive reading template slide not found. "
                f"Add {TOKEN_KO} to the responsive slide in the template."
            )
        if last_index is None:
            raise RuntimeError(
                "Responsive reading last-line template slide not found. "
                f"Add {TOKEN_KO_LAST} to the last responsive slide in the template."
            )

        deleted = _delete_extra_responsive_slides(presentation_obj, regular_index, last_index)

        line_count = len(lines)
        if line_count == 1:
            presentation_obj.Slides(regular_index).Delete()
            if last_index > regular_index:
                last_index -= 1
            _fill_responsive_slide(presentation_obj.Slides(last_index), lines[0], last=True)
        else:
            regular_count = line_count - 1
            for _ in range(regular_count - 1):
                presentation_obj.Slides(regular_index).Duplicate()
                if last_index > regular_index:
                    last_index += 1

            for index in range(regular_count):
                slide = presentation_obj.Slides(regular_index + index)
                _fill_responsive_slide(slide, lines[index], last=False)

            _fill_responsive_slide(
                presentation_obj.Slides(last_index),
                lines[-1],
                last=True,
            )

        return {
            "responsive_slides": line_count,
            "regular_slides": max(line_count - 1, 0),
            "last_slide": 1,
            "deleted_placeholders": deleted,
            "regular_template_index": regular_index,
            "last_template_index": last_index,
        }

    if presentation is not None:
        return _insert(presentation)

    from ppt_com_session import powerpoint_edit_session

    with powerpoint_edit_session(presentation_path) as presentation_obj:
        return _insert(presentation_obj)
