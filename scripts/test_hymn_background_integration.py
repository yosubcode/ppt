"""Integration test: hymn background image on slides 34-36 and hymn sections."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from hymn_merger import (
    CONTENT_BACKGROUND_TRANSPARENCY,
    FIXED_BACKGROUND_SLIDE_INDICES,
    TITLE_BACKGROUND_TRANSPARENCY,
)
from week_generator import GenerateOptions, generate_week_ppt, load_week_data

JSON = ROOT / "config" / "extracted_week.json"
BACKGROUND = ROOT / "input_hyms" / "1.png"
OUTPUT = ROOT / "output" / "test_hymn_background.pptx"

MSO_FILL_PICTURE = 6


def _find_worship_hymn_indices(presentation) -> list[int]:
    indices: list[int] = []
    for slide_index in range(1, presentation.Slides.Count + 1):
        slide = presentation.Slides(slide_index)
        texts: list[str] = []
        for shape_index in range(1, slide.Shapes.Count + 1):
            shape = slide.Shapes(shape_index)
            if shape.HasTextFrame and shape.TextFrame.HasText:
                texts.append(shape.TextFrame.TextRange.Text)
        if any("WORSHIP HYMN" in text for text in texts):
            indices.append(slide_index)
    return indices


def _background_info(slide) -> tuple[int, float]:
    fill = slide.Background.Fill
    fill_type = int(fill.Type)
    transparency = float(fill.Transparency)
    return fill_type, transparency


def _shifted_fixed_indices(
    *,
    youth_deleted_index: int | None,
    hymn1_inserted: int,
    hymn1_template_index: int = 18,
    hymn2_inserted: int = 0,
    hymn2_template_index: int = 46,
    pre_hymn_slide_delta: int = 0,
) -> tuple[int, ...]:
    """Map template fixed-bg slides to their final indices after worship edits."""
    shifted: list[int] = []
    for template_index in FIXED_BACKGROUND_SLIDE_INDICES:
        pos = template_index + pre_hymn_slide_delta
        if youth_deleted_index is not None and template_index > youth_deleted_index:
            pos -= 1
        if template_index > hymn2_template_index:
            pos += hymn2_inserted
        if template_index > hymn1_template_index:
            pos += hymn1_inserted
        shifted.append(pos)
    return tuple(shifted)


def _pre_hymn_slide_delta(result) -> int:
    """Net slides inserted before the fixed-bg block by responsive/scripture."""
    delta = 0
    responsive_stats = result.responsive_stats or {}
    scripture_stats = result.scripture_stats or {}
    if responsive_stats:
        line_count = int(responsive_stats.get("responsive_slides", 0))
        if line_count > 1:
            delta += line_count - 2
        delta -= int(responsive_stats.get("deleted_placeholders", 0))
    if scripture_stats:
        verse_count = int(scripture_stats.get("verse_slides", 0))
        if verse_count > 1:
            delta += verse_count - 2
        delta -= int(scripture_stats.get("deleted_placeholders", 0))
    return delta


def _find_empty_picture_background_slides(
    presentation,
    *,
    transparency: float,
) -> list[int]:
    indices: list[int] = []
    for slide_index in range(1, presentation.Slides.Count + 1):
        slide = presentation.Slides(slide_index)
        fill_type, fill_transparency = _background_info(slide)
        if fill_type != MSO_FILL_PICTURE:
            continue
        if abs(fill_transparency - transparency) > 0.02:
            continue

        texts: list[str] = []
        for shape_index in range(1, slide.Shapes.Count + 1):
            shape = slide.Shapes(shape_index)
            if shape.HasTextFrame and shape.TextFrame.HasText:
                text = shape.TextFrame.TextRange.Text.strip()
                if text:
                    texts.append(text)
        if not texts:
            indices.append(slide_index)
    return indices


class HymnBackgroundIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not JSON.is_file():
            raise unittest.SkipTest(f"Missing test data: {JSON}")
        if not BACKGROUND.is_file():
            raise unittest.SkipTest(f"Missing background image: {BACKGROUND}")
        if not (ROOT / "templates" / "Sunday_Template.pptx").is_file():
            raise unittest.SkipTest("Missing Sunday_Template.pptx")

        data = load_week_data(json_path=JSON)
        options = GenerateOptions(
            output=OUTPUT,
            translate=False,
            insert_responsive=False,
            insert_scripture=False,
            insert_sermon_verses=False,
            insert_hymns=True,
            generate_thumbnail=False,
            hymn_background_image=BACKGROUND,
        )
        cls.result = generate_week_ppt(data, options)
        cls.output_path = Path(cls.result.output_path)

    def test_generation_stats(self) -> None:
        stats = self.result.hymn_stats or {}
        self.assertEqual(stats.get("background_image"), BACKGROUND.name)
        self.assertEqual(stats.get("fixed_background_slides"), 3)
        self.assertGreater(stats.get("hymn1", 0), 0)
        self.assertGreater(stats.get("hymn2", 0), 0)

    def test_backgrounds_via_com(self) -> None:
        import win32com.client

        powerpoint = win32com.client.Dispatch("PowerPoint.Application")
        try:
            powerpoint.Visible = 0
        except Exception:
            pass

        presentation = powerpoint.Presentations.Open(
            str(self.output_path.resolve()),
            ReadOnly=True,
            Untitled=False,
            WithWindow=False,
        )
        try:
            hymn_indices = _find_worship_hymn_indices(presentation)
            self.assertGreaterEqual(len(hymn_indices), 2, hymn_indices)
            hymn1_index, hymn2_index = hymn_indices[0], hymn_indices[1]

            hymn1_inserted = int(self.result.hymn_stats["hymn1"])
            hymn2_inserted = int(self.result.hymn_stats["hymn2"])
            youth_stats = self.result.youth_sermon_stats or {}
            deleted_index = (
                int(youth_stats["deleted_index"])
                if youth_stats.get("youth_sermon_slide") == "deleted"
                else None
            )
            shifted_fixed_indices = _shifted_fixed_indices(
                youth_deleted_index=deleted_index,
                hymn1_inserted=hymn1_inserted,
                hymn2_inserted=hymn2_inserted,
            )

            for slide_index in shifted_fixed_indices:
                fill_type, transparency = _background_info(presentation.Slides(slide_index))
                self.assertEqual(
                    fill_type,
                    MSO_FILL_PICTURE,
                    f"slide {slide_index} should use picture background",
                )
                self.assertAlmostEqual(
                    transparency,
                    CONTENT_BACKGROUND_TRANSPARENCY,
                    places=2,
                    msg=f"slide {slide_index} transparency",
                )

            for title_index in (hymn1_index, hymn2_index):
                fill_type, transparency = _background_info(presentation.Slides(title_index))
                self.assertEqual(fill_type, MSO_FILL_PICTURE)
                self.assertAlmostEqual(transparency, TITLE_BACKGROUND_TRANSPARENCY, places=2)

            for slide_index in range(hymn1_index + 1, hymn1_index + hymn1_inserted + 1):
                fill_type, transparency = _background_info(presentation.Slides(slide_index))
                self.assertEqual(fill_type, MSO_FILL_PICTURE)
                self.assertAlmostEqual(transparency, CONTENT_BACKGROUND_TRANSPARENCY, places=2)

            for slide_index in range(hymn2_index + 1, hymn2_index + hymn2_inserted + 1):
                fill_type, transparency = _background_info(presentation.Slides(slide_index))
                self.assertEqual(fill_type, MSO_FILL_PICTURE)
                self.assertAlmostEqual(transparency, CONTENT_BACKGROUND_TRANSPARENCY, places=2)

            print(
                f"OK fixed slides -> {shifted_fixed_indices}; "
                f"hymn1 title={hymn1_index}, inserted={hymn1_inserted}; "
                f"hymn2 title={hymn2_index}, inserted={hymn2_inserted}"
            )
        finally:
            presentation.Close()
            powerpoint.Quit()


class HymnBackgroundFullPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not JSON.is_file():
            raise unittest.SkipTest(f"Missing test data: {JSON}")
        if not BACKGROUND.is_file():
            raise unittest.SkipTest(f"Missing background image: {BACKGROUND}")
        if not (ROOT / "templates" / "Sunday_Template.pptx").is_file():
            raise unittest.SkipTest("Missing Sunday_Template.pptx")

        data = load_week_data(json_path=JSON)
        options = GenerateOptions(
            output=ROOT / "output" / "test_hymn_background_full.pptx",
            translate=False,
            insert_responsive=True,
            insert_scripture=True,
            insert_sermon_verses=True,
            insert_hymns=True,
            generate_thumbnail=False,
            hymn_background_image=BACKGROUND,
        )
        cls.result = generate_week_ppt(data, options)
        cls.output_path = Path(cls.result.output_path)

    def test_fixed_backgrounds_survive_slide_shifts(self) -> None:
        import win32com.client

        powerpoint = win32com.client.Dispatch("PowerPoint.Application")
        try:
            powerpoint.Visible = 0
        except Exception:
            pass

        presentation = powerpoint.Presentations.Open(
            str(self.output_path.resolve()),
            ReadOnly=True,
            Untitled=False,
            WithWindow=False,
        )
        try:
            empty_bg_slides = _find_empty_picture_background_slides(
                presentation,
                transparency=CONTENT_BACKGROUND_TRANSPARENCY,
            )
            self.assertGreaterEqual(
                len(empty_bg_slides),
                3,
                f"expected at least 3 empty 70% bg slides, found {empty_bg_slides}",
            )

            youth_stats = self.result.youth_sermon_stats or {}
            deleted_index = (
                int(youth_stats["deleted_index"])
                if youth_stats.get("youth_sermon_slide") == "deleted"
                else None
            )
            shifted_fixed_indices = _shifted_fixed_indices(
                youth_deleted_index=deleted_index,
                hymn1_inserted=int(self.result.hymn_stats["hymn1"]),
                hymn2_inserted=int(self.result.hymn_stats["hymn2"]),
                pre_hymn_slide_delta=_pre_hymn_slide_delta(self.result),
            )

            for slide_index in shifted_fixed_indices:
                fill_type, transparency = _background_info(
                    presentation.Slides(slide_index)
                )
                self.assertEqual(fill_type, MSO_FILL_PICTURE)
                self.assertAlmostEqual(
                    transparency,
                    CONTENT_BACKGROUND_TRANSPARENCY,
                    places=2,
                    msg=f"slide {slide_index} transparency",
                )

            print(f"OK empty fixed-bg slides at {shifted_fixed_indices}")
        finally:
            presentation.Close()
            powerpoint.Quit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
