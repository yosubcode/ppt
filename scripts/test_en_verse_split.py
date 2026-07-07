"""Test English verse split with line-per-verse format."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from scripture_parser import parse_scripture_range, split_bulk_verse_text, build_scripture_verses

EN = """6 Then the people of Judah came to Joshua at Gilgal. And Caleb the son of Jephunneh the Kenizzite said to him, "You know what the Lord said to Moses the man of God in Kadesh-barnea concerning you and me.
7 I was forty years old when Moses the servant of the Lord sent me from Kadesh-barnea to spy out the land, and I brought him word again as it was in my heart.
8 But my brothers who went up with me made the heart of the people melt; yet I wholly followed the Lord my God.
9 And Moses swore on that day, saying, 'Surely the land on which your foot has trodden shall be an inheritance for you and your children forever, because you have wholly followed the Lord my God. '
10 And now, behold, the Lord has kept me alive, just as he said, these forty-five years since the time that the Lord spoke this word to Moses, while Israel walked in the wilderness. And now, behold, I am this day eighty-five years old.
11 I am still as strong today as I was in the day that Moses sent me; my strength now is as my strength was then, for war and for going and coming.
12 So now give me this hill country of which the Lord spoke on that day, for you heard on that day how the Anakim were there, with great fortified cities. It may be that the Lord will be with me, and I shall drive them out just as the Lord said. "
13 Then Joshua blessed him, and he gave Hebron to Caleb the son of Jephunneh for an inheritance.
14 Therefore Hebron became the inheritance of Caleb the son of Jephunneh the Kenizzite to this day, because he wholly followed the Lord, the God of Israel.
15 Now the name of Hebron formerly was Kiriath-arba. (Arba was the greatest man among the Anakim. ) And the land had rest from war."""

parsed = parse_scripture_range("수14:6-15")
en_map = split_bulk_verse_text(EN, parsed)

print("EN verses found:", len(en_map), "keys:", list(en_map.keys()))
assert len(en_map) == 10, f"Expected 10 verses, got {len(en_map)}"
assert list(en_map.keys()) == list(range(6, 16))

expected_starts = {
    6: "Then the people of Judah",
    7: "I was forty years old",
    8: "But my brothers",
    9: "And Moses swore",
    10: "And now, behold, the Lord has kept me alive",
    11: "I am still as strong today",
    12: "So now give me this hill country",
    13: "Then Joshua blessed him",
    14: "Therefore Hebron became",
    15: "Now the name of Hebron",
}

for verse_num, start in expected_starts.items():
    text = en_map[verse_num]
    assert text.startswith(start), f"Verse {verse_num}: expected start {start!r}, got {text[:60]!r}"
    print(f"OK 14:{verse_num} -> {text[:80]}...")

data = {
    "scripture": "수14:6-15",
    "scripture_chapter": 14,
    "scripture_verse_start": 6,
    "scripture_verse_end": 15,
    "scripture_en_text": EN,
}
verses = build_scripture_verses(data)
print(f"\nbuild_scripture_verses: {len(verses)} entries")
print("All English line-per-verse tests passed.")
