"""Test ESV API bracket-style verse splitting."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from app_paths import load_app_env
from bible_fetcher import fetch_english_verses
from scripture_parser import parse_scripture_range, split_bulk_verse_text

load_app_env()

ESV = (
    '[6] Then the people of Judah came to Joshua at Gilgal. And Caleb the son of Jephunneh '
    'the Kenizzite said to him, "You know what the LORD said to Moses the man of God in '
    'Kadesh-barnea concerning you and me. [7] I was forty years old when Moses the servant '
    'of the LORD sent me from Kadesh-barnea to spy out the land, and I brought him word '
    'again as it was in my heart. [8] But my brothers who went up with me made the heart '
    'of the people melt; yet I wholly followed the LORD my God. [9] And Moses swore on that '
    "day, saying, 'Surely the land on which your foot has trodden shall be an inheritance "
    "for you and your children forever, because you have wholly followed the LORD my God.' "
    "[10] And now, behold, the LORD has kept me alive, just as he said, these forty-five "
    "years since the time that the LORD spoke this word to Moses, while Israel walked in "
    "the wilderness. And now, behold, I am this day eighty-five years old. [11] I am still "
    "as strong today as I was in the day that Moses sent me; my strength now is as my "
    "strength was then, for war and for going and coming. [12] So now give me this hill "
    "country of which the LORD spoke on that day, for you heard on that day how the Anakim "
    "were there, with great fortified cities. It may be that the LORD will be with me, and "
    'I shall drive them out just as the LORD said."\n\n'
    "Then Joshua blessed him, and he gave Hebron to Caleb the son of Jephunneh for an "
    "inheritance. [14] Therefore Hebron became the inheritance of Caleb the son of Jephunneh "
    "the Kenizzite to this day, because he wholly followed the LORD, the God of Israel. "
    "[15] Now the name of Hebron formerly was Kiriath-arba. (Arba was the greatest man "
    "among the Anakim.) And the land had rest from war."
)

parsed = parse_scripture_range("Joshua 14:6-15")
split_map = split_bulk_verse_text(ESV, parsed)
print("split count:", len(split_map), "keys:", sorted(split_map))

assert len(split_map) == 10, f"expected 10 verses, got {len(split_map)}"
assert split_map[13].startswith("Then Joshua blessed"), split_map[13]
assert split_map[12].startswith("So now give me"), split_map[12]
print("OK verse 13:", split_map[13][:80])

fetched = fetch_english_verses("Joshua 14:6-15", parsed)
print("fetch count:", len(fetched))
assert len(fetched) == 10, f"expected 10 fetched verses, got {len(fetched)}"
assert fetched[13].startswith("Then Joshua blessed"), fetched[13]
print("All ESV bracket split tests passed.")
