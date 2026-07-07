"""Insert hymn PPT slides into worship presentation using PowerPoint COM."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hymn_resolver import resolve_hymn_path

HYMN1_END_MARKERS = (
    "CONGREGATIONAL PRAYER",
    "대  표  기  도",
    "{{PRAYER}}",
)

HYMN2_END_MARKERS = (
    "BENEDICTION",
    "축   도",
    "축  도",
    "{{BENEDICTION}}",
)

# PowerPoint RGB(255, 255, 255)
WHITE_RGB = 16777215

FIXED_BACKGROUND_SLIDE_INDICES = (34, 35, 36)
TITLE_BACKGROUND_TRANSPARENCY = 0.35
CONTENT_BACKGROUND_TRANSPARENCY = 0.70

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


def _resolve_background_image(image_path: str | Path) -> str:
    path = Path(image_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Hymn background image not found: {path}")
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError(f"Unsupported hymn background image type: {path.suffix}")
    return str(path)


def _set_white_slide_background(slide) -> None:
    """Remove slide master background and apply solid white fill."""
    slide.FollowMasterBackground = 0
    try:
        slide.DisplayMasterShapes = 0
    except Exception:
        pass

    fill = slide.Background.Fill
    fill.Visible = True
    fill.Solid()
    fill.ForeColor.RGB = WHITE_RGB


def _set_image_slide_background(slide, image_path: str, transparency: float) -> None:
    """Apply a picture background with the given transparency (0=opaque, 1=transparent)."""
    slide.FollowMasterBackground = 0
    try:
        slide.DisplayMasterShapes = 0
    except Exception:
        pass

    fill = slide.Background.Fill
    fill.Visible = True
    fill.UserPicture(image_path)
    fill.Transparency = transparency


def _apply_fixed_worship_backgrounds(presentation, image_path: str) -> int:
    """Apply the selected image to slides 34-36 before hymn insertion shifts indices."""
    applied = 0
    for slide_index in FIXED_BACKGROUND_SLIDE_INDICES:
        if slide_index > presentation.Slides.Count:
            continue
        _set_image_slide_background(
            presentation.Slides(slide_index),
            image_path,
            CONTENT_BACKGROUND_TRANSPARENCY,
        )
        applied += 1
    return applied


def _apply_content_background_after_insert(
    presentation,
    title_index: int,
    inserted_count: int,
    *,
    image_path: str | None,
) -> None:
    """Apply background to slides inserted immediately after a hymn title slide."""
    start_index = title_index + 1
    end_index = title_index + inserted_count
    for slide_index in range(start_index, end_index + 1):
        slide = presentation.Slides(slide_index)
        if image_path:
            _set_image_slide_background(
                slide,
                image_path,
                CONTENT_BACKGROUND_TRANSPARENCY,
            )
        else:
            _set_white_slide_background(slide)


def _get_slide_text(slide) -> str:
    parts: list[str] = []
    for shape_index in range(1, slide.Shapes.Count + 1):
        shape = slide.Shapes(shape_index)
        if shape.HasTextFrame and shape.TextFrame.HasText:
            parts.append(shape.TextFrame.TextRange.Text)
    return "\n".join(parts)


def _find_worship_hymn_title_indices(presentation) -> list[int]:
    """Return 1-based slide indices for WORSHIP HYMN title slides."""
    indices: list[int] = []
    for slide_index in range(1, presentation.Slides.Count + 1):
        slide_text = _get_slide_text(presentation.Slides(slide_index))
        if "WORSHIP HYMN" in slide_text:
            indices.append(slide_index)
    return indices


def _delete_following_placeholder_slides(
    presentation,
    title_index: int,
    end_markers: tuple[str, ...],
) -> int:
    """Delete slides after hymn title until the next worship section marker."""
    deleted = 0
    while title_index + 1 <= presentation.Slides.Count:
        next_slide = presentation.Slides(title_index + 1)
        next_text = _get_slide_text(next_slide)

        if any(marker in next_text for marker in end_markers):
            break

        next_slide.Delete()
        deleted += 1

    return deleted


def _count_slides(presentation, hymn_path: Path) -> int:
    path = Path(hymn_path)
    if path.suffix.lower() == ".pptx":
        from pptx import Presentation

        return len(Presentation(path).slides)

    hymn_presentation = presentation.Application.Presentations.Open(
        str(path.resolve()),
        WithWindow=False,
        ReadOnly=True,
    )
    try:
        return hymn_presentation.Slides.Count
    finally:
        hymn_presentation.Close()


def _insert_hymn_after_title(
    presentation,
    title_index: int,
    hymn_path: Path,
    end_markers: tuple[str, ...],
    *,
    background_image: str | None = None,
) -> int:
    """Insert hymn slides after title slide. Returns number of inserted slides."""
    if background_image:
        _set_image_slide_background(
            presentation.Slides(title_index),
            background_image,
            TITLE_BACKGROUND_TRANSPARENCY,
        )

    _delete_following_placeholder_slides(presentation, title_index, end_markers)
    slide_count = _count_slides(presentation, hymn_path)
    presentation.Slides.InsertFromFile(
        str(hymn_path.resolve()),
        title_index,
        1,
        slide_count,
    )
    _apply_content_background_after_insert(
        presentation,
        title_index,
        slide_count,
        image_path=background_image,
    )
    return slide_count


def apply_fixed_worship_backgrounds_only(
    presentation_path: str | Path,
    background_image: str | Path,
    *,
    presentation: Any | None = None,
) -> dict[str, int | str]:
    """Apply the selected image to slides 34-36 without inserting hymns."""
    image_path = _resolve_background_image(background_image)

    def _apply(presentation_obj) -> dict[str, int | str]:
        applied = _apply_fixed_worship_backgrounds(presentation_obj, image_path)
        return {
            "fixed_background_slides": applied,
            "background_image": Path(image_path).name,
        }

    if presentation is not None:
        return _apply(presentation)

    from ppt_com_session import powerpoint_edit_session

    with powerpoint_edit_session(presentation_path) as presentation_obj:
        return _apply(presentation_obj)


def insert_hymns(
    presentation_path: str | Path,
    data: dict[str, Any],
    hymns_dir: str | Path,
    *,
    background_image: str | Path | None = None,
    presentation: Any | None = None,
) -> dict[str, int | str]:
    """
    Insert hymn1 and hymn2 PPT slides into the worship presentation.

    When background_image is set, apply it to hymn title slides at 35% transparency
    and inserted hymn slides at 70% transparency.

    Fixed slides 34-36 must be handled earlier in week_generator before any slide
    insertion shifts their indices.
    """
    hymns_root = Path(hymns_dir)
    hymn1_path = resolve_hymn_path(hymns_root, str(data["hymn1"]))
    hymn2_path = resolve_hymn_path(hymns_root, str(data["hymn2"]))
    image_path = _resolve_background_image(background_image) if background_image else None

    def _insert(presentation_obj) -> dict[str, int | str]:
        title_indices = _find_worship_hymn_title_indices(presentation_obj)
        if len(title_indices) < 2:
            raise RuntimeError(
                f"Expected at least 2 WORSHIP HYMN title slides, found {len(title_indices)}"
            )

        hymn1_index, hymn2_index = title_indices[0], title_indices[1]

        # Insert later hymn first so earlier slide indices stay valid.
        hymn2_inserted = _insert_hymn_after_title(
            presentation_obj,
            hymn2_index,
            hymn2_path,
            HYMN2_END_MARKERS,
            background_image=image_path,
        )
        hymn1_inserted = _insert_hymn_after_title(
            presentation_obj,
            hymn1_index,
            hymn1_path,
            HYMN1_END_MARKERS,
            background_image=image_path,
        )
        result = {
            "hymn1": hymn1_inserted,
            "hymn2": hymn2_inserted,
            "hymn1_file": hymn1_path.name,
            "hymn2_file": hymn2_path.name,
        }
        if image_path:
            result["background_image"] = Path(image_path).name
        return result

    if presentation is not None:
        return _insert(presentation)

    from ppt_com_session import powerpoint_edit_session

    with powerpoint_edit_session(presentation_path) as presentation_obj:
        return _insert(presentation_obj)
