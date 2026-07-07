"""PowerPoint COM helpers that preserve template text formatting."""

from __future__ import annotations

from pathlib import Path


def normalize_slide_text(text: str) -> str:
    """Collapse whitespace for slide body text."""
    return " ".join(str(text).split())


def replace_token_in_text_range(
    text_range,
    token: str,
    value: str,
    *,
    normalize: bool = True,
) -> bool:
    """Replace a token inside a TextRange while keeping the matched run formatting."""
    if token not in text_range.Text:
        return False

    replacement = normalize_slide_text(value) if normalize else str(value)
    search_after = 0
    replaced = False

    while True:
        found = text_range.Find(token, search_after, -1, 0)
        if found is None or found.Text != token:
            break

        found.Text = replacement
        replaced = True
        search_after = found.Start + len(replacement)
        if search_after >= len(text_range.Text):
            break

    return replaced


def replace_token_in_shape(
    shape,
    token: str,
    value: str,
    *,
    normalize: bool = True,
) -> bool:
    """Replace a placeholder token in a shape without resetting the whole text frame."""
    if not shape.HasTextFrame or not shape.TextFrame.HasText:
        return False

    return replace_token_in_text_range(
        shape.TextFrame.TextRange,
        token,
        value,
        normalize=normalize,
    )


def save_presentation_with_embedded_fonts(
    presentation,
    file_path: str | Path | None = None,
) -> None:
    """Save the presentation and embed TrueType fonts for consistent layout on other PCs."""
    path = str(Path(file_path or presentation.FullName).resolve())

    mso_true = -1
    pp_save_as_default = 11
    try:
        from win32com.client import constants

        mso_true = constants.msoTrue
        pp_save_as_default = constants.ppSaveAsDefault
    except Exception:
        pass

    try:
        presentation.SaveAs(path, pp_save_as_default, mso_true)
        return
    except Exception:
        presentation.Save()
