"""Print weekly data extracted from bulletin and sermon PDFs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pdf_parser import parse_week_from_pdfs


def main() -> int:
    data = parse_week_from_pdfs()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
