"""Check responsive_readings/100-137 for empty files and duplicates."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "responsive_readings"
START = 100
END = 137


def normalize(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def main() -> None:
    entries: list[dict] = []
    for number in range(START, END + 1):
        path = ROOT / f"{number}.txt"
        if not path.is_file():
            entries.append({"num": number, "path": path, "empty": True, "missing": True, "norm": "", "hash": None})
            continue
        raw = path.read_text(encoding="utf-8")
        norm = normalize(raw)
        lines = [line for line in raw.splitlines() if line.strip()]
        entries.append(
            {
                "num": number,
                "path": path,
                "empty": not norm,
                "missing": False,
                "lines": len(lines),
                "chars": len(norm),
                "norm": norm,
                "hash": hashlib.sha256(norm.encode("utf-8")).hexdigest() if norm else None,
            }
        )

    filled = [entry for entry in entries if not entry.get("missing") and not entry["empty"]]
    empty = [entry["num"] for entry in entries if not entry.get("missing") and entry["empty"]]
    missing = [entry["num"] for entry in entries if entry.get("missing")]

    print(f"=== Summary {START}-{END} ===")
    print(f"Filled: {len(filled)}/{END - START + 1}")
    if missing:
        print(f"Missing: {missing}")
    if empty:
        print(f"Empty: {empty}")

    print("\n=== Line counts ===")
    for entry in filled:
        print(f"  {entry['num']:3d}: {entry['lines']} lines, {entry['chars']} chars")

    by_hash: dict[str, list[int]] = {}
    for entry in filled:
        by_hash.setdefault(entry["hash"], []).append(entry["num"])

    exact = [nums for nums in by_hash.values() if len(nums) > 1]
    print("\n=== Exact duplicate groups ===")
    if not exact:
        print("None")
    else:
        for nums in sorted(exact):
            print(f"  {nums}")

    by_first: dict[str, list[int]] = {}
    for entry in filled:
        first = entry["norm"].split("\n", 1)[0]
        by_first.setdefault(first, []).append(entry["num"])

    first_dupes = [nums for nums in by_first.values() if len(nums) > 1]
    print("\n=== Same first line ===")
    if not first_dupes:
        print("None")
    else:
        for nums in sorted(first_dupes):
            first_line = by_first[next(k for k, v in by_first.items() if v == nums)]
            preview = first_line[:55] + "..." if len(first_line) > 55 else first_line
            print(f"  {nums}: {preview}")

    print("\n=== Highly similar pairs (>=90% line Jaccard) ===")
    found = False
    for index, left in enumerate(filled):
        left_lines = set(left["norm"].split("\n"))
        for right in filled[index + 1 :]:
            right_lines = set(right["norm"].split("\n"))
            union = left_lines | right_lines
            if not union:
                continue
            score = len(left_lines & right_lines) / len(union)
            if score >= 0.9:
                found = True
                print(
                    f"  {left['num']} vs {right['num']}: {score:.0%} "
                    f"({len(left_lines & right_lines)}/{len(union)} unique lines)"
                )
    if not found:
        print("None")


if __name__ == "__main__":
    main()
