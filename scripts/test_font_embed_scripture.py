"""Integration test: scripture COM merge uses Malgun Gothic and embeds fonts on save."""

from __future__ import annotations

import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from week_generator import GenerateOptions, generate_week_ppt, load_week_data


OUTPUT = ROOT / "output" / "test_font_embed_scripture.pptx"
JSON = ROOT / "config" / "extracted_week.json"
SCRIPTURE_FONT = "Malgun Gothic"


def _generate() -> Path:
    data = load_week_data(json_path=JSON)
    options = GenerateOptions(
        output=OUTPUT,
        translate=False,
        insert_hymns=False,
        insert_responsive=False,
        insert_scripture=True,
        insert_sermon_verses=True,
        generate_thumbnail=False,
    )
    result = generate_week_ppt(data, options)
    if not result.scripture_stats:
        raise RuntimeError("scripture_stats missing; scripture insert did not run")
    if not result.sermon_verse_stats:
        raise RuntimeError("sermon_verse_stats missing; sermon verse COM did not run")
    return Path(result.output_path)


def _embedded_font_entries(pptx_path: Path) -> list[str]:
    with zipfile.ZipFile(pptx_path) as archive:
        return [
            name
            for name in archive.namelist()
            if name.startswith("ppt/fonts/") and not name.endswith("/")
        ]


def _ko_en_verse_shape_fonts_via_com(pptx_path: Path) -> list[str]:
    """Return fonts on long KO/EN verse bodies (scripture + sermon part slides)."""
    import win32com.client

    target = str(pptx_path.resolve())
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
    fonts: list[str] = []
    try:
        for slide_index in range(1, presentation.Slides.Count + 1):
            slide = presentation.Slides(slide_index)
            for shape_index in range(1, slide.Shapes.Count + 1):
                shape = slide.Shapes(shape_index)
                if not shape.HasTextFrame or not shape.TextFrame.HasText:
                    continue
                text = shape.TextFrame.TextRange.Text.strip()
                if len(text) < 40:
                    continue
                if "{{" in text:
                    continue
                if any(
                    marker in text
                    for marker in (
                        "Then Moses",
                        "When they came",
                        "And he cried",
                        "Then they came",
                        "모세가 홍해",
                        "마라에 이르렀",
                        "백성이 모세",
                        "이르시되 너희",
                        "그들이 엘림",
                    )
                ):
                    fonts.append(str(shape.TextFrame.TextRange.Font.Name))
    finally:
        presentation.Close()
        powerpoint.Quit()
    return fonts


class FontEmbedScriptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not JSON.is_file():
            raise unittest.SkipTest(f"Missing test data: {JSON}")
        if not (ROOT / "templates" / "Sunday_Template.pptx").is_file():
            raise unittest.SkipTest("Missing Sunday_Template.pptx")
        cls.output_path = _generate()

    def test_output_file_exists(self) -> None:
        self.assertTrue(self.output_path.is_file(), self.output_path)

    def test_embedded_fonts_present(self) -> None:
        entries = _embedded_font_entries(self.output_path)
        self.assertTrue(
            entries,
            "ppt/fonts/ entries missing; SaveAs embed may not have run",
        )
        print(f"Embedded font files: {len(entries)}")
        for entry in entries[:5]:
            print(f"  {entry}")

    def test_scripture_font_is_malgun_gothic_com(self) -> None:
        fonts = _ko_en_verse_shape_fonts_via_com(self.output_path)
        self.assertTrue(fonts, "No scripture/sermon KO/EN shapes found via COM")
        non_portable = [name for name in fonts if SCRIPTURE_FONT.lower() not in name.lower()]
        print(f"COM verse KO/EN fonts ({len(fonts)}): {sorted(set(fonts))}")
        self.assertFalse(
            non_portable,
            f"Unexpected verse fonts: {sorted(set(non_portable))}",
        )

    def test_scripture_text_has_line_breaks(self) -> None:
        import win32com.client

        target = str(self.output_path.resolve())
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
            found_multiline = False
            for slide_index in range(1, presentation.Slides.Count + 1):
                slide = presentation.Slides(slide_index)
                for shape_index in range(1, slide.Shapes.Count + 1):
                    shape = slide.Shapes(shape_index)
                    if not shape.HasTextFrame or not shape.TextFrame.HasText:
                        continue
                    text = shape.TextFrame.TextRange.Text
                    if "마라" in text and "\r" in text:
                        found_multiline = True
                        line_count = text.count("\r") + 1
                        print(f"Multiline KO shape on slide {slide_index}: {line_count} lines")
                        break
            self.assertTrue(found_multiline, "Expected hard line breaks in long KO verse text")
        finally:
            presentation.Close()
            powerpoint.Quit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
