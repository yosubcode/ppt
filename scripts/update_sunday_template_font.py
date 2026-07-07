"""Set every text shape in Sunday_Template.pptx to Malgun Gothic."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ppt_com_text import save_presentation_with_embedded_fonts
from scripture_merger import SCRIPTURE_FONT_NAME

TEMPLATE = ROOT / "templates" / "Sunday_Template.pptx"
MSO_GROUP = 6


def _apply_font_to_text_range(text_range, *, stats: dict[str, int]) -> None:
    try:
        size = float(text_range.Font.Size)
    except Exception:
        size = 0.0

    text_range.Font.Name = SCRIPTURE_FONT_NAME
    if size > 0:
        text_range.Font.Size = size
    stats["text_ranges"] += 1


def _apply_font_to_shape(shape, *, stats: dict[str, int]) -> None:
    if shape.Type == MSO_GROUP:
        for index in range(1, shape.GroupItems.Count + 1):
            _apply_font_to_shape(shape.GroupItems(index), stats=stats)
        return

    if shape.HasTable:
        table = shape.Table
        for row in range(1, table.Rows.Count + 1):
            for col in range(1, table.Columns.Count + 1):
                cell = table.Cell(row, col)
                if cell.Shape.HasTextFrame and cell.Shape.TextFrame.HasText:
                    _apply_font_to_text_range(cell.Shape.TextFrame.TextRange, stats=stats)
        stats["tables"] += 1
        return

    if not shape.HasTextFrame:
        return

    if shape.TextFrame.HasText:
        _apply_font_to_text_range(shape.TextFrame.TextRange, stats=stats)
        stats["shapes"] += 1


def update_template_font(template_path: Path = TEMPLATE) -> dict[str, int]:
    import win32com.client

    target = str(template_path.resolve())
    stats = {"slides": 0, "shapes": 0, "tables": 0, "text_ranges": 0}

    powerpoint = win32com.client.Dispatch("PowerPoint.Application")
    try:
        powerpoint.Visible = 0
    except Exception:
        pass

    presentation = powerpoint.Presentations.Open(
        target,
        ReadOnly=False,
        Untitled=False,
        WithWindow=False,
    )
    try:
        for slide_index in range(1, presentation.Slides.Count + 1):
            slide = presentation.Slides(slide_index)
            stats["slides"] += 1
            for shape_index in range(1, slide.Shapes.Count + 1):
                _apply_font_to_shape(slide.Shapes(shape_index), stats=stats)

        save_presentation_with_embedded_fonts(presentation, target)
        return stats
    finally:
        presentation.Close()
        powerpoint.Quit()


def verify_fonts(template_path: Path = TEMPLATE) -> list[str]:
    import win32com.client

    target = str(template_path.resolve())
    fonts: set[str] = set()

    powerpoint = win32com.client.Dispatch("PowerPoint.Application")
    try:
        powerpoint.Visible = 0
    except Exception:
        pass

    presentation = powerpoint.Presentations.Open(
        target,
        ReadOnly=True,
        Untitled=False,
        WithWindow=False,
    )
    try:
        for slide_index in range(1, presentation.Slides.Count + 1):
            slide = presentation.Slides(slide_index)
            for shape_index in range(1, slide.Shapes.Count + 1):
                shape = slide.Shapes(shape_index)
                if shape.Type == MSO_GROUP:
                    for index in range(1, shape.GroupItems.Count + 1):
                        item = shape.GroupItems(index)
                        if item.HasTextFrame and item.TextFrame.HasText:
                            fonts.add(str(item.TextFrame.TextRange.Font.Name))
                    continue
                if shape.HasTextFrame and shape.TextFrame.HasText:
                    fonts.add(str(shape.TextFrame.TextRange.Font.Name))
    finally:
        presentation.Close()
        powerpoint.Quit()

    return sorted(fonts)


def main() -> int:
    if not TEMPLATE.is_file():
        print(f"Template not found: {TEMPLATE}")
        return 1

    stats = update_template_font()
    fonts = verify_fonts()
    print(f"Updated {TEMPLATE}")
    print(f"  slides={stats['slides']} shapes={stats['shapes']} tables={stats['tables']}")
    print(f"  font={SCRIPTURE_FONT_NAME}")
    print(f"  remaining font names: {fonts}")
    non_target = [name for name in fonts if SCRIPTURE_FONT_NAME.lower() not in name.lower()]
    if non_target:
        print(f"  WARNING: non-unified fonts still present: {non_target}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
