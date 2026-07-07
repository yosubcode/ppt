"""Remove or keep the Youth Sermon slide based on bulletin data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

YOUTH_SERMON_MARKER = "{{SERMON_TITLE2}}"


def _get_slide_text(slide) -> str:
    parts: list[str] = []
    for shape_index in range(1, slide.Shapes.Count + 1):
        shape = slide.Shapes(shape_index)
        if shape.HasTextFrame and shape.TextFrame.HasText:
            parts.append(shape.TextFrame.TextRange.Text)
    return "\n".join(parts)


def _find_youth_sermon_slide_index(presentation) -> int | None:
    for slide_index in range(1, presentation.Slides.Count + 1):
        slide_text = _get_slide_text(presentation.Slides(slide_index))
        if YOUTH_SERMON_MARKER in slide_text:
            return slide_index
    return None


def apply_youth_sermon_slide(
    presentation_path: str | Path,
    data: dict[str, Any],
    *,
    presentation: Any | None = None,
) -> dict[str, int | str] | None:
    """Delete the Youth Sermon slide when bulletin PDF has no Youth Sermon title."""
    title = str(data.get("sermon_title2", "")).strip()
    if title:
        return {"youth_sermon_slide": "kept", "title": title}

    def _apply(presentation_obj) -> dict[str, int | str]:
        slide_index = _find_youth_sermon_slide_index(presentation_obj)
        if slide_index is None:
            return {"youth_sermon_slide": "not_found"}

        presentation_obj.Slides(slide_index).Delete()
        return {"youth_sermon_slide": "deleted", "deleted_index": slide_index}

    if presentation is not None:
        return _apply(presentation)

    from ppt_com_session import powerpoint_edit_session

    with powerpoint_edit_session(presentation_path) as presentation_obj:
        return _apply(presentation_obj)
