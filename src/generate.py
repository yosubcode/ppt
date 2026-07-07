"""CLI entry point for weekly worship PPT generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from week_generator import (
    DEFAULT_EXTRACTED_JSON,
    DEFAULT_HYMNS_DIR,
    DEFAULT_INPUT2_DIR,
    DEFAULT_INPUT_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_TEMPLATE,
    GenerateOptions,
    generate_week_ppt,
    load_week_data,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate weekly worship PPT from template and JSON/PDF data."
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Weekly data JSON file. With --from-pdf, merges overrides on top of extracted PDF data.",
    )
    parser.add_argument(
        "--from-pdf",
        action="store_true",
        help="Extract weekly data from input/ bulletin PDF and input2/ sermon PDF",
    )
    parser.add_argument(
        "--bulletin-pdf",
        type=Path,
        default=None,
        help=f"Bulletin PDF path (default: first PDF in {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--sermon-pdf",
        type=Path,
        default=None,
        help=f"Sermon notes PDF path (default: first PDF in {DEFAULT_INPUT2_DIR})",
    )
    parser.add_argument(
        "--save-json",
        type=Path,
        default=None,
        help=(
            "Write extracted/merged weekly JSON to this path "
            f"(with --from-pdf defaults to {DEFAULT_EXTRACTED_JSON})"
        ),
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help=f"Template PPT file (default: {DEFAULT_TEMPLATE})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output PPT path (default: output/{date}_주일예배.pptx)",
    )
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Skip auto-translation of _eng fields from Korean source fields",
    )
    parser.add_argument(
        "--no-hymns",
        action="store_true",
        help="Skip inserting hymn PPT slides from hymns/ folder",
    )
    parser.add_argument(
        "--no-responsive",
        action="store_true",
        help="Skip generating responsive reading slides from template slide 7",
    )
    parser.add_argument(
        "--no-scripture",
        action="store_true",
        help="Skip generating scripture verse slides from template slide 30",
    )
    parser.add_argument(
        "--hymns-dir",
        type=Path,
        default=DEFAULT_HYMNS_DIR,
        help=f"Hymn PPT library folder (default: {DEFAULT_HYMNS_DIR})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    json_path = args.json
    if not args.from_pdf and json_path is None:
        print("Provide --from-pdf or --json.", file=sys.stderr)
        return 1

    save_json_path = None
    if args.from_pdf:
        save_json_path = args.save_json if args.save_json is not None else DEFAULT_EXTRACTED_JSON

    try:
        data = load_week_data(
            from_pdf=args.from_pdf,
            bulletin_pdf=args.bulletin_pdf,
            sermon_pdf=args.sermon_pdf,
            json_path=json_path,
            input_dir=DEFAULT_INPUT_DIR,
            input2_dir=DEFAULT_INPUT2_DIR,
        )
    except (FileNotFoundError, ValueError) as error:
        print(f"Failed to load weekly data: {error}", file=sys.stderr)
        return 1

    options = GenerateOptions(
        template=args.template,
        output=args.output,
        output_dir=DEFAULT_OUTPUT_DIR,
        translate=not args.no_translate,
        insert_responsive=not args.no_responsive,
        insert_scripture=not args.no_scripture,
        insert_hymns=not args.no_hymns,
        hymns_dir=args.hymns_dir,
        save_json=save_json_path,
    )

    try:
        result = generate_week_ppt(data, options)
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Generation failed: {error}", file=sys.stderr)
        return 1

    if result.saved_json:
        print(f"Saved extracted JSON: {result.saved_json}")

    print(f"Generated: {result.output_path}")
    print(f"Placeholder replacements: {result.replaced_count}")
    if result.translated_fields:
        print(f"Auto-translated fields: {', '.join(result.translated_fields)}")
    if result.remaining_tokens:
        print(f"Unreplaced tokens: {', '.join(result.remaining_tokens)}")
    if result.responsive_stats:
        print(f"Inserted responsive reading: {result.responsive_stats['responsive_slides']} slides")
    if result.scripture_stats:
        print(f"Inserted scripture verses: {result.scripture_stats['verse_slides']} slides")
    if result.youth_sermon_stats:
        print(f"Youth Sermon slide: {result.youth_sermon_stats.get('youth_sermon_slide')}")
    if result.hymn_stats:
        print(
            "Inserted hymns: "
            f"{result.hymn_stats['hymn1_file']} ({result.hymn_stats['hymn1']} slides), "
            f"{result.hymn_stats['hymn2_file']} ({result.hymn_stats['hymn2']} slides)"
        )
    if result.thumbnail_path:
        print(f"Generated thumbnail: {result.thumbnail_path}")
        print(f"Thumbnail placeholder replacements: {result.thumbnail_replaced_count}")
        if result.thumbnail_remaining_tokens:
            print(f"Thumbnail unreplaced tokens: {', '.join(result.thumbnail_remaining_tokens)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
