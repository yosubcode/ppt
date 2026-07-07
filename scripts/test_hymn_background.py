"""Tests for hymn background slide targeting."""

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
    _resolve_background_image,
)


class HymnBackgroundTests(unittest.TestCase):
    def test_fixed_slide_indices(self) -> None:
        self.assertEqual(FIXED_BACKGROUND_SLIDE_INDICES, (34, 35, 36))

    def test_transparency_values(self) -> None:
        self.assertEqual(TITLE_BACKGROUND_TRANSPARENCY, 0.35)
        self.assertEqual(CONTENT_BACKGROUND_TRANSPARENCY, 0.70)

    def test_resolve_background_image_rejects_missing(self) -> None:
        with self.assertRaises(FileNotFoundError):
            _resolve_background_image(ROOT / "input_hyms" / "missing.png")


if __name__ == "__main__":
    unittest.main()
