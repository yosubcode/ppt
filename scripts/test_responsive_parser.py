"""Tests for responsive reading line parsing."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from responsive_parser import build_responsive_lines, strip_responsive_scripture_references


class ResponsiveParserTests(unittest.TestCase):
    def test_strip_dagati_and_verse_range(self) -> None:
        line = "(다같이) 그들이 성문에서 그들의 원수와 담판할 때에 수치를 당하지 아니하리로다 (1 - 5)"
        self.assertEqual(
            strip_responsive_scripture_references(line),
            "그들이 성문에서 그들의 원수와 담판할 때에 수치를 당하지 아니하리로다",
        )

    def test_strip_book_reference(self) -> None:
        line = "볼지어다 내가 세상 끝날까지 너희와 항상 함께 있으리라 하시니라 (마 28 : 19 - 20)"
        self.assertEqual(
            strip_responsive_scripture_references(line),
            "볼지어다 내가 세상 끝날까지 너희와 항상 함께 있으리라 하시니라",
        )

    def test_build_lines_removes_all_parentheses(self) -> None:
        data = {
            "responsive_ko_text": (
                "(다같이) 여호와께서 집을 세우지 아니하시면 세우는 자의 수고가 헛되며 (1 - 5)\n"
                "이는 내 사랑하는 아들이요 내 기뻐하는 자라 하시니라 (마 3 : 16 - 17)"
            ),
            "translate": False,
            "responsive_en_lines": [
                "Unless the LORD builds the house (1 - 5)",
                "This is my beloved Son (Matt 3:16-17)",
            ],
        }
        lines = build_responsive_lines(data, translate=False)
        self.assertEqual(len(lines), 2)
        self.assertNotIn("(", lines[0]["ko"])
        self.assertNotIn("(", lines[1]["ko"])
        self.assertNotIn("(", lines[0]["en"])
        self.assertNotIn("(", lines[1]["en"])


if __name__ == "__main__":
    unittest.main()
