"""Shared PowerPoint COM session for batch worship PPT editing."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from ppt_com_text import save_presentation_with_embedded_fonts

# PowerPoint PpEntryEffect.ppEffectNone
PP_EFFECT_NONE = 0


def _create_powerpoint_app():
    import win32com.client

    powerpoint = win32com.client.Dispatch("PowerPoint.Application")
    try:
        powerpoint.Visible = 0
    except Exception:
        pass
    return powerpoint


def _open_presentation(powerpoint, presentation_path: str | Path):
    return powerpoint.Presentations.Open(
        str(Path(presentation_path).resolve()),
        ReadOnly=False,
        Untitled=False,
        WithWindow=False,
    )


def clear_all_slide_transitions(presentation) -> int:
    """Set every slide transition effect to None. Returns slide count updated."""
    updated = 0
    for slide_index in range(1, presentation.Slides.Count + 1):
        transition = presentation.Slides(slide_index).SlideShowTransition
        transition.EntryEffect = PP_EFFECT_NONE
        updated += 1
    return updated


@contextmanager
def powerpoint_edit_session(
    presentation_path: str | Path,
) -> Generator[Any, None, None]:
    """Open PowerPoint once, yield the presentation, and save once on exit."""
    target_path = str(Path(presentation_path).resolve())
    powerpoint = _create_powerpoint_app()
    presentation = _open_presentation(powerpoint, target_path)
    try:
        yield presentation
        save_presentation_with_embedded_fonts(presentation, target_path)
    finally:
        presentation.Close()
        powerpoint.Quit()


def needs_powerpoint_session(
    opts,
    data: dict,
    *,
    background_path: Path | None,
) -> bool:
    """Return True when at least one COM editing step will run."""
    if getattr(opts, "clear_slide_transitions", True):
        return True
    if background_path:
        return True
    if not str(data.get("sermon_title2", "")).strip():
        return True
    if opts.insert_hymns:
        return True
    if opts.insert_responsive:
        return True
    if opts.insert_scripture:
        return True
    if opts.insert_sermon_verses:
        from sermon_verse_merger import SERMON_VERSE_TOKEN_FIELDS

        if any(str(data.get(field, "")).strip() for _token, field in SERMON_VERSE_TOKEN_FIELDS):
            return True
    return False
