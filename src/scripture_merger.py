"""Insert scripture verse slides using the verse template slide."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ppt_com_text import replace_token_in_shape
from scripture_parser import verses_ready_for_insert

TOKEN_REF = "{{VERSE_REF}}"
TOKEN_KO = "{{VERSE_KO}}"
TOKEN_EN = "{{VERSE_EN}}"
TOKEN_REF_LAST = "{{VERSE_REF_LAST}}"
TOKEN_KO_LAST = "{{VERSE_KO_LAST}}"
TOKEN_EN_LAST = "{{VERSE_EN_LAST}}"

SCRIPTURE_SECTION_END_MARKERS = (
    "새신교회찬양대",
    "PRAISETHELORD",
    "찬양",
    "{{SERMON_TITLE}}",
    "{{SERMON_TITLE2}}",
    "WORSHIPHYMN",
)

# PowerPoint COM constants
PP_ALIGN_LEFT = 1
PP_AUTOSIZE_NONE = 0
PP_AUTOSIZE_SHAPE_TO_FIT = 1
KO_EN_GAP_PT = 14
ALTOGETHER_EN_GAP_PT = 4
TEXT_BOX_PADDING_PT = 4
SCRIPTURE_FONT_NAME = "Malgun Gothic"


def _normalize_marker(text: str) -> str:
    return re.sub(r"\s+", "", text).upper()


def _get_slide_text(slide) -> str:
    parts: list[str] = []
    for shape_index in range(1, slide.Shapes.Count + 1):
        shape = slide.Shapes(shape_index)
        if shape.HasTextFrame and shape.TextFrame.HasText:
            parts.append(shape.TextFrame.TextRange.Text)
    return "\n".join(parts)


def _is_scripture_section_end(text: str) -> bool:
    normalized = _normalize_marker(text)
    return any(marker in normalized for marker in SCRIPTURE_SECTION_END_MARKERS)


def _slide_has_regular_template(text: str) -> bool:
    return TOKEN_REF in text and TOKEN_REF_LAST not in text


def _slide_has_last_template(text: str) -> bool:
    return TOKEN_REF_LAST in text


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


def _delete_extra_scripture_slides(
    presentation,
    regular_index: int,
    last_index: int,
) -> int:
    """Remove placeholder slides after the last verse template until the next section."""
    deleted = 0
    while last_index + 1 <= presentation.Slides.Count:
        next_slide = presentation.Slides(last_index + 1)
        next_text = _get_slide_text(next_slide)
        if _is_scripture_section_end(next_text):
            break
        if _slide_has_last_template(next_text) or _slide_has_regular_template(next_text):
            break
        next_slide.Delete()
        deleted += 1
    return deleted


def _last_en_token(text: str) -> str | None:
    if TOKEN_EN_LAST in text:
        return TOKEN_EN_LAST
    if TOKEN_EN in text:
        return TOKEN_EN
    return None


def _find_token_shapes(slide, *, last: bool = False) -> dict[str, Any]:
    shapes: dict[str, Any] = {}
    for shape_index in range(1, slide.Shapes.Count + 1):
        shape = slide.Shapes(shape_index)
        if not shape.HasTextFrame:
            continue
        text = shape.TextFrame.TextRange.Text

        if last:
            if TOKEN_REF_LAST in text:
                shapes["ref"] = shape
            elif TOKEN_KO_LAST in text:
                shapes["ko"] = shape
            else:
                en_token = _last_en_token(text)
                if en_token:
                    shapes["en"] = shape
                    shapes["en_token"] = en_token
            continue

        if TOKEN_REF in text and TOKEN_REF_LAST not in text:
            shapes["ref"] = shape
        elif TOKEN_KO in text and TOKEN_KO_LAST not in text:
            shapes["ko"] = shape
        elif TOKEN_EN in text and TOKEN_EN_LAST not in text:
            shapes["en"] = shape
    return shapes


def _normalize_verse_text(text: str) -> str:
    """Use a single wrapped paragraph so PowerPoint does not stack extra lines."""
    return " ".join(str(text).split())


_WORD_SPLIT_MAX_PASSES = 100


def _plain_verse_text(text: str) -> str:
    return _normalize_verse_text(text.replace("\r", " ").replace("\n", " "))


def _line_boundary_fragments(curr_text: str, next_text: str) -> tuple[str, str]:
    curr = curr_text.rstrip("\r\n")
    nxt = next_text.lstrip("\r\n")
    if not curr or not nxt:
        return "", ""

    space_index = curr.rfind(" ")
    suffix = curr[space_index + 1 :] if space_index >= 0 else curr

    prefix_chars: list[str] = []
    for char in nxt:
        if char == " ":
            break
        prefix_chars.append(char)
    prefix = "".join(prefix_chars)
    return suffix, prefix


def _is_mid_word_line_break(suffix: str, prefix: str, plain_text: str) -> bool:
    if not suffix or not prefix:
        return False
    if not (suffix[-1].isalnum() and prefix[0].isalnum()):
        return False

    combined = suffix + prefix
    idx = plain_text.find(combined)
    if idx < 0:
        return False

    mid = idx + len(suffix)
    return not (mid < len(plain_text) and plain_text[mid] == " ")


def _text_range_slice(text_range, start: int, end: int) -> str:
    if end < start:
        return ""
    return text_range.Characters(start, end - start + 1).Text


def _get_wrapped_line_ranges(text_range) -> list[tuple[int, int]]:
    """Return 1-based character ranges for each rendered line in a text range."""
    raw = text_range.Text
    if not raw:
        return []

    length = len(raw)
    line_start = 1
    prev_top: float | None = None
    ranges: list[tuple[int, int]] = []
    pos = 1

    while pos <= length:
        char = raw[pos - 1]
        if char in "\r\n":
            if pos > line_start:
                ranges.append((line_start, pos - 1))
            line_start = pos + 1
            pos += 1
            prev_top = None
            continue

        curr_top = float(text_range.Characters(pos, 1).BoundTop)
        if prev_top is not None and abs(curr_top - prev_top) > 1.0:
            ranges.append((line_start, pos - 1))
            line_start = pos
        prev_top = curr_top
        pos += 1

    end = length
    while end >= line_start and raw[end - 1] in "\r\n":
        end -= 1
    if end >= line_start:
        ranges.append((line_start, end))
    return ranges


def _word_break_insert_position(line_start: int, curr_text: str) -> int:
    curr = curr_text.rstrip("\r\n")
    space_index = curr.rfind(" ")
    word_start_in_line = 0 if space_index < 0 else space_index + 1
    return line_start + word_start_in_line


def _fix_first_mid_word_line_break(text_range) -> bool:
    line_ranges = _get_wrapped_line_ranges(text_range)
    if len(line_ranges) <= 1:
        return False

    plain_text = _plain_verse_text(text_range.Text)

    for line_index in range(len(line_ranges) - 1):
        start1, end1 = line_ranges[line_index]
        start2, end2 = line_ranges[line_index + 1]
        curr_text = _text_range_slice(text_range, start1, end1)
        nxt_text = _text_range_slice(text_range, start2, end2)
        suffix, prefix = _line_boundary_fragments(curr_text, nxt_text)
        if not _is_mid_word_line_break(suffix, prefix, plain_text):
            continue

        insert_at = _word_break_insert_position(start1, curr_text)
        if insert_at <= 1:
            continue
        if text_range.Characters(insert_at - 1, 1).Text in "\r\n":
            continue

        text_range.Characters(insert_at, 0).InsertBefore("\r")
        return True

    return False


def _prevent_mid_word_line_breaks(text_range) -> None:
    """Move split words to the next line; repeat until every line ends cleanly."""
    for _ in range(_WORD_SPLIT_MAX_PASSES):
        if not _fix_first_mid_word_line_break(text_range):
            break


def _capture_font(text_range) -> tuple[str, float]:
    """Use a portable Windows Korean font; keep the template point size."""
    default_size = 32.0
    try:
        size = float(text_range.Font.Size)
    except Exception:
        size = default_size
    if size <= 0:
        size = default_size
    return SCRIPTURE_FONT_NAME, size


def _apply_text_shape(shape, text: str, *, prevent_word_splits: bool = False) -> None:
    text_frame = shape.TextFrame
    text_frame.WordWrap = True
    text_frame.MarginBottom = 0
    text_frame.MarginTop = 0
    text_frame.MarginLeft = 0
    text_frame.MarginRight = 0
    text_frame.AutoSize = PP_AUTOSIZE_SHAPE_TO_FIT

    text_range = text_frame.TextRange
    font_name, font_size = _capture_font(text_range)
    text_range.Text = _normalize_verse_text(text)
    text_range.Font.Name = font_name
    text_range.Font.Size = font_size

    fmt = text_range.ParagraphFormat
    fmt.Alignment = PP_ALIGN_LEFT
    fmt.SpaceBefore = 0
    fmt.SpaceAfter = 0

    if prevent_word_splits:
        _prevent_mid_word_line_breaks(text_range)

    _resize_shape_to_text(shape)


def _replace_token_in_shape(
    shape,
    token: str,
    value: str,
    *,
    prevent_word_splits: bool = False,
) -> None:
    text_frame = shape.TextFrame
    text_frame.WordWrap = True
    text_frame.AutoSize = PP_AUTOSIZE_SHAPE_TO_FIT
    if not replace_token_in_shape(shape, token, value):
        return
    text_range = text_frame.TextRange
    font_name, font_size = _capture_font(text_range)
    text_range.Font.Name = font_name
    text_range.Font.Size = font_size
    if prevent_word_splits:
        _prevent_mid_word_line_breaks(text_range)
    _resize_shape_to_text(shape)


def _resize_shape_to_text(shape) -> None:
    """Lock shape height to the rendered text height so wrapped lines do not overlap."""
    text_range = shape.TextFrame.TextRange
    bound_height = float(text_range.BoundHeight)
    if bound_height <= 0:
        return
    shape.TextFrame.AutoSize = PP_AUTOSIZE_NONE
    shape.Height = bound_height + TEXT_BOX_PADDING_PT


def _shape_bottom(shape) -> float:
    return float(shape.Top) + float(shape.Height)


def _align_shape_bottom(shape, bottom: float) -> None:
    shape.Top = bottom - float(shape.Height)


def _finalize_wrapped_text_shape(shape) -> None:
    """Re-run word-split prevention after final width/position are applied."""
    text_frame = shape.TextFrame
    text_frame.WordWrap = True
    _prevent_mid_word_line_breaks(text_frame.TextRange)
    _resize_shape_to_text(shape)


def _finalize_bottom_aligned_text_shape(shape, bottom: float) -> None:
    """Re-run word-split prevention after final width/position are applied."""
    _finalize_wrapped_text_shape(shape)
    _align_shape_bottom(shape, bottom)


def _layout_ko_en_shapes(
    ko_shape,
    en_shape,
    *,
    en_bottom: float | None = None,
    gap_pt: float = KO_EN_GAP_PT,
) -> None:
    """Place English below Korean or bottom-align it to a fixed anchor."""
    en_shape.Left = ko_shape.Left
    en_shape.Width = ko_shape.Width
    if en_bottom is not None:
        _align_shape_bottom(en_shape, en_bottom)
        _finalize_bottom_aligned_text_shape(en_shape, en_bottom)
        return

    en_shape.Top = ko_shape.Top + ko_shape.Height + gap_pt
    _finalize_wrapped_text_shape(en_shape)


def _find_congregation_labels(slide) -> dict[str, Any]:
    """Find fixed [기도문] / [Altogether] label shapes on the last verse slide."""
    labels: dict[str, Any] = {}
    for shape_index in range(1, slide.Shapes.Count + 1):
        shape = slide.Shapes(shape_index)
        if not shape.HasTextFrame or not shape.TextFrame.HasText:
            continue
        text = shape.TextFrame.TextRange.Text.replace("\r", "").strip()
        if text == "[기도문]":
            labels["prayer"] = shape
        elif text == "[Altogether]":
            labels["altogether"] = shape
    return labels


def _layout_last_verse_slide(
    slide,
    shapes: dict[str, Any],
    *,
    en_bottom: float | None = None,
) -> None:
    """Keep KO at the top; bottom-align EN and stack Altogether directly above EN."""
    labels = _find_congregation_labels(slide)
    ko_shape = shapes.get("ko")
    en_shape = shapes.get("en")
    altogether_shape = labels.get("altogether")

    if ko_shape:
        ko_shape.TextFrame.WordWrap = True
        _resize_shape_to_text(ko_shape)

    if en_shape:
        if ko_shape:
            en_shape.Left = ko_shape.Left
            en_shape.Width = ko_shape.Width
        en_shape.TextFrame.WordWrap = True
        _resize_shape_to_text(en_shape)
        if en_bottom is not None:
            _align_shape_bottom(en_shape, en_bottom)
            _finalize_bottom_aligned_text_shape(en_shape, en_bottom)

    if altogether_shape and en_shape:
        altogether_shape.Top = (
            float(en_shape.Top) - ALTOGETHER_EN_GAP_PT - float(altogether_shape.Height)
        )
    elif altogether_shape and en_bottom is not None:
        _align_shape_bottom(altogether_shape, en_bottom)


def _fill_verse_slide(slide, verse: dict[str, Any], *, last: bool = False) -> None:
    shapes = _find_token_shapes(slide, last=last)
    ref = str(verse.get("ref", ""))
    ko = str(verse.get("ko", ""))
    en = str(verse.get("en", ""))

    en_bottom = _shape_bottom(shapes["en"]) if "en" in shapes else None

    if last:
        if "ref" in shapes:
            replace_token_in_shape(shapes["ref"], TOKEN_REF_LAST, ref)
        if "ko" in shapes:
            _replace_token_in_shape(
                shapes["ko"],
                TOKEN_KO_LAST,
                ko,
                prevent_word_splits=True,
            )
        if "en" in shapes:
            en_token = shapes.get("en_token", TOKEN_EN_LAST)
            _replace_token_in_shape(
                shapes["en"],
                en_token,
                en,
                prevent_word_splits=True,
            )
        _layout_last_verse_slide(slide, shapes, en_bottom=en_bottom)
        return

    if "ref" in shapes:
        _apply_text_shape(shapes["ref"], ref)
    if "ko" in shapes:
        _apply_text_shape(shapes["ko"], ko, prevent_word_splits=True)
    if "en" in shapes:
        _apply_text_shape(shapes["en"], en, prevent_word_splits=True)
    if "ko" in shapes and "en" in shapes and en_bottom is not None:
        _layout_ko_en_shapes(shapes["ko"], shapes["en"], en_bottom=en_bottom)


def insert_scripture_verses(
    presentation_path: str | Path,
    data: dict[str, Any],
    *,
    presentation: Any | None = None,
) -> dict[str, int | str] | None:
    """Duplicate regular verse slides and fill the last verse on the LAST template."""
    verses = verses_ready_for_insert(data)
    if not verses:
        return None

    def _insert(presentation_obj) -> dict[str, int | str]:
        regular_index = _find_regular_template_index(presentation_obj)
        last_index = _find_last_template_index(presentation_obj)
        if regular_index is None:
            raise RuntimeError(
                "Verse template slide not found. "
                f"Add {TOKEN_REF} to the verse slide in the template."
            )
        if last_index is None:
            raise RuntimeError(
                "Verse last-line template slide not found. "
                f"Add {TOKEN_REF_LAST} to the last verse slide in the template."
            )

        deleted = _delete_extra_scripture_slides(presentation_obj, regular_index, last_index)

        verse_count = len(verses)
        if verse_count == 1:
            presentation_obj.Slides(regular_index).Delete()
            if last_index > regular_index:
                last_index -= 1
            _fill_verse_slide(presentation_obj.Slides(last_index), verses[0], last=True)
        else:
            regular_count = verse_count - 1
            for _ in range(regular_count - 1):
                presentation_obj.Slides(regular_index).Duplicate()
                if last_index > regular_index:
                    last_index += 1

            for index in range(regular_count):
                slide = presentation_obj.Slides(regular_index + index)
                _fill_verse_slide(slide, verses[index], last=False)

            _fill_verse_slide(
                presentation_obj.Slides(last_index),
                verses[-1],
                last=True,
            )

        return {
            "verse_slides": verse_count,
            "regular_slides": max(verse_count - 1, 0),
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
