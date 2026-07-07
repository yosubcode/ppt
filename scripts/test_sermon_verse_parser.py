"""Unit tests for sermon part verse parsing."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sermon_verse_parser import (
    align_ko_and_en_to_pdf_quote,
    parse_sermon_outline,
    parse_sermon_part_verses,
    restore_ko_quote_spacing,
)


SAMPLE_TEXT = """
1. 하나님여호와께충성했음(8절)
(오직하나님말씀좇는신앙)
2. 도전하는신앙(10-11절)
(담대한신앙=도전을두려워하지않는믿음)
3. 헤브론을기업으로받음(12-13절)
(하나님의뜻을이루어감)
하나님 여호와께 충성했음
1
8
= "나와함께올라갔던내형제들은백성의간담을녹게하였으나나는내하나님여호와께충성하였으므로"
도전하는 신앙
2
10-11절= "....오늘내가팔십오세로되"
헤브론을 기업으로 받음
3
12-13절= "여호수아가여분네의아들갈렙을위하여축복하고헤브론을그에게주어기업을삽게하매"
"""

EQUALS_OUTLINE_TEXT = """
1. 곳간헐고더크게짓자함(16-18절)
= 탐욕가득하였음
2. 먹고마시고즐거워하자함(19)
= 쾌락에취함(구원의즐거움을모르는자)
3. 하나님께부요치못한자임(21)
= 인생목적이재물에있는자(천국갈준비가
안된사람)
곳간을 헐고 더 크게 짓자 함
1
16~18= "...한부자가그밭에소출이풍성하매심중에생각하여이르되내가곡식쌓아둘곳이없으니"
     먹고 마시고 즐거워하자 함
2
19= "또내가내영혼에게이르되영혼아여러해쓸물건을많이쌓아두었으니평안히쉬고먹고마시고즐거워하자하리라"
    하나님께 부요하지 못한 자임
3
20~21절= "하나님은이르시되어리석은자여오늘밤에네영혼을도로찾으리니그러면네준비한것이누구의것이되겠느냐"
"""


class SermonVerseParserTests(unittest.TestCase):
    def test_parse_three_parts(self) -> None:
        parts = parse_sermon_part_verses(SAMPLE_TEXT)
        self.assertEqual(parts[1]["verse_start"], 8)
        self.assertEqual(parts[1]["verse_end"], 8)
        self.assertIn("충성", parts[1]["verse_ko_quote"])
        self.assertFalse(parts[1]["verse_ko_truncated"])

        self.assertEqual(parts[2]["verse_start"], 10)
        self.assertEqual(parts[2]["verse_end"], 11)
        self.assertTrue(parts[2]["verse_ko_truncated"])

        self.assertEqual(parts[3]["verse_start"], 12)
        self.assertEqual(parts[3]["verse_end"], 13)
        self.assertIn("헤브론", parts[3]["verse_ko_quote"])

    def test_parse_equals_outline_format(self) -> None:
        outline = parse_sermon_outline(EQUALS_OUTLINE_TEXT)
        self.assertEqual(len(outline), 3)
        self.assertEqual(outline[0][1], "곳간헐고더크게짓자함")
        self.assertEqual(outline[0][2], "16-18절")
        self.assertIn("탐욕", outline[0][3])

        parts = parse_sermon_part_verses(EQUALS_OUTLINE_TEXT)
        self.assertEqual(parts[1]["verse_start"], 16)
        self.assertEqual(parts[1]["verse_end"], 18)
        self.assertIn("한부자", parts[1]["verse_ko_quote"])
        self.assertEqual(parts[2]["verse_start"], 19)
        self.assertIn("영혼", parts[2]["verse_ko_quote"])
        self.assertEqual(parts[3]["verse_start"], 20)
        self.assertEqual(parts[3]["verse_end"], 21)
        self.assertIn("리석은자", parts[3]["verse_ko_quote"])

    def test_align_truncated_quote(self) -> None:
        ko_full = (
            "이제 보소서 여호와께서 이 말씀을 모세에게 이르신 때로부터 이스라엘이 광야에서 방황한 "
            "이 사십오 년 동안을 여호와께서 말씀하신 대로 나를 생존하게 하셨나이다 오늘 내가 팔십오 세로되 "
            "모세가 나를 보내던 날과 같이 오늘도 내가 여전히 강건하니"
        )
        en_full = (
            "And now, behold, the LORD has kept me alive, just as he said, these forty-five years "
            "since the time that the LORD spoke this word to Moses, while Israel walked in the wilderness. "
            "And now, behold, I am this day eighty-five years old. "
            "I am still as strong today as I was in the day that Moses sent me"
        )
        pdf_quote = "....오늘내가팔십오세로되"
        ko_text, en_text = align_ko_and_en_to_pdf_quote(
            pdf_quote,
            {1: ko_full},
            {1: en_full},
        )
        self.assertIn("오늘 내가 팔십오", ko_text)
        self.assertNotIn("이제 보소서", ko_text)
        self.assertIn("eighty-five", en_text.lower())


    def test_restore_ko_quote_keeps_pdf_typo_suffix(self) -> None:
        bible = (
            "여호수아가 여분네의 아들 갈렙을 위하여 축복하고 "
            "헤브론을 그에게 주어 기업을 삼게 하매"
        )
        pdf = "여호수아가여분네의아들갈렙을위하여축복하고헤브론을그에게주어기업을삽게하매"
        restored = restore_ko_quote_spacing(pdf, bible)
        self.assertIn("기업을", restored)
        self.assertIn("삽게", restored)
        self.assertIn("하매", restored)
        self.assertNotEqual(
            restored.rstrip(),
            "여호수아가 여분네의 아들 갈렙을 위하여 축복하고 헤브론을 그에게 주어 기업을",
        )

    def test_restore_ko_quote_spacing_uses_bible_throughout(self) -> None:
        bible = (
            "그들이 엘림에 이르니 거기에 물 샘 열둘과 종려나무 일흔 그루가 있는지라 "
            "거기서 그들이 그 물 곁에 장막을 치니라"
        )
        pdf = (
            "그들이엘림에이르니거기에물샘열둘과종려나무일흔그루가있는지라"
            "그들이그물곁에장막을치니 라"
        )
        restored = restore_ko_quote_spacing(pdf, bible)
        self.assertNotIn("그들이그물", restored)
        self.assertIn("그 물 곁", restored)
        self.assertIn("장막을 치니라", restored)

    def test_partial_verse_en_ends_on_sentence_boundary(self) -> None:
        ko_verse = (
            "모세가 여호와께 부르짖었더니 여호와께서 그에게 한 나무를 가리키시니 "
            "그가 물에 던지니 물이 달게 되었더라 거기서 여호와께서 그들을 위하여 "
            "법도와 율례를 정하시고 그들을 시험하실새"
        )
        en_verse = (
            "Then he cried to Yahweh. Yahweh showed him a tree, and he threw it into the waters, "
            "and the waters were made sweet. There he made a statute and an ordinance for them, "
            "and there he tested them;"
        )
        pdf_quote = (
            "모세가여호와께부르짖었더니여호와께서그에게한나무를가리키시니"
            "그가물에던지니물이달게되었더라"
        )
        _ko, en_text = align_ko_and_en_to_pdf_quote(
            pdf_quote,
            {25: ko_verse},
            {25: en_verse},
        )
        self.assertIn("sweet", en_text.lower())
        self.assertNotIn("statute", en_text.lower())
        self.assertNotIn("tested", en_text.lower())
        self.assertTrue(en_text.rstrip()[-1] in ".!?;")
        self.assertFalse(en_text.rstrip().split()[-1].lower() in {"a", "h", "w", "the"})


if __name__ == "__main__":
    unittest.main()
