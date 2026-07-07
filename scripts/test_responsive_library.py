"""Verify responsive reading library loading."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from responsive_library import enrich_responsive_data, load_responsive_text, parse_responsive_number

assert parse_responsive_number("137번") == 137
assert parse_responsive_number("9") == 9

text = load_responsive_text(137)
assert text is not None
assert "예수께서 세례를" in text
assert text.count("\n") == 9

enriched = enrich_responsive_data({"responsive": "137번"})
assert enriched["responsive_ko_text"] == text

unchanged = enrich_responsive_data({"responsive": "137번", "responsive_ko_text": "manual"})
assert unchanged["responsive_ko_text"] == "manual"

print("OK")
