"""Tests for bskorea HTML annotation stripping."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bible_books import resolve_bible_book
from bible_fetcher import _clean_html_text, fetch_korean_verses
from scripture_parser import parse_scripture_range

LUKE_13_RAW = (
    "<font size='1'></font>무리 중에 한 사람이 이르되 선생님 내 "
    "<font size=2><a class=comment href=\"#\" onClick=\"return clickPopUp('D_226027_1', event)\" >"
    "<font size=2>2)</font></a></font>형을 명하여 유산을 나와 나누게 하소서 하니 \n\n"
    "<div id='D_226027_1' class=D2 onclick=\"popDown2('D_226027_1')\" "
    "style='display:none;z-index:100'>또는 동생</div></font>"
)


class BskoreaCleanTests(unittest.TestCase):
    def test_strips_footnote_markers_and_popup_text(self) -> None:
        cleaned = _clean_html_text(LUKE_13_RAW)
        self.assertEqual(
            cleaned,
            "무리 중에 한 사람이 이르되 선생님 내 형을 명하여 유산을 나와 나누게 하소서 하니",
        )
        self.assertNotIn("2)", cleaned)
        self.assertNotIn("동생", cleaned)

    def test_fetch_luke_12_13(self) -> None:
        book = resolve_bible_book("눅12:13-21")
        parsed = parse_scripture_range("눅12:13-21")
        verses = fetch_korean_verses(book.bskorea_code, parsed)
        self.assertIn("형을", verses[13])
        self.assertNotIn("2)", verses[13])
        self.assertNotIn("동생", verses[13])


if __name__ == "__main__":
    unittest.main()
