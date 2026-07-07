"""Verify Korean scripture spacing after bskorea HTML cleanup."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bible_fetcher import _clean_html_text, fetch_korean_verses
from scripture_parser import ScriptureRange

RAW = (
    '<font class="area">헤브론</font>이 <font class="area">그니스</font> 사람 '
    '<font class="name">여분네</font>의 아들 <font class="name">갈렙</font>의 기업이 되어 '
    '오늘까지 이르렀으니 이는 그가 <font class="area">이스라엘</font>의 '
    '하나님 여호와를 온전히 좇았음이라 </font>'
)
EXPECTED = (
    "헤브론이 그니스 사람 여분네의 아들 갈렙의 기업이 되어 "
    "오늘까지 이르렀으니 이는 그가 이스라엘의 하나님 여호와를 온전히 좇았음이라"
)

cleaned = _clean_html_text(RAW)
assert cleaned == EXPECTED, f"unit mismatch:\n  got:      {cleaned}\n  expected: {EXPECTED}"

scripture_range = ScriptureRange(book=None, chapter=14, start=14, end=14)
live = fetch_korean_verses("jos", scripture_range)[14]
assert live == EXPECTED, f"live fetch mismatch:\n  got:      {live}\n  expected: {EXPECTED}"

print("OK")
