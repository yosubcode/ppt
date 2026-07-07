"""Shared weekly PPT generation logic for CLI and GUI."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bible_fetcher import enrich_sermon_part_verses
from hymn_merger import apply_fixed_worship_backgrounds_only, insert_hymns
from korean_text import normalize_week_sermon_text
from pdf_parser import parse_week_from_pdfs
from ppt_builder import apply_weekly_data, merge_week_data, validate_required_fields
from sermon_verse_merger import SERMON_VERSE_TOKEN_FIELDS, apply_sermon_part_verses
from youth_sermon_merger import apply_youth_sermon_slide
from responsive_library import enrich_responsive_data
from responsive_merger import insert_responsive_reading
from responsive_parser import build_responsive_lines
from scripture_merger import insert_scripture_verses
from scripture_parser import apply_scripture_range_to_data, build_scripture_verses
from app_paths import (
    get_app_root,
    get_template_path,
    get_thumbnail_template_path,
)
from ppt_com_session import needs_powerpoint_session, powerpoint_edit_session
from thumbnail_builder import generate_thumbnail_ppt

ROOT = get_app_root()
DEFAULT_TEMPLATE = get_template_path()
DEFAULT_THUMBNAIL_TEMPLATE = get_thumbnail_template_path()
DEFAULT_OUTPUT_DIR = ROOT / "output"
DEFAULT_HYMNS_DIR = ROOT / "hymns"
DEFAULT_INPUT_HYMS_DIR = ROOT / "input_hyms"
DEFAULT_INPUT_DIR = ROOT / "input"
DEFAULT_INPUT2_DIR = ROOT / "input2"
DEFAULT_EXTRACTED_JSON = ROOT / "config" / "extracted_week.json"

EDITABLE_FIELDS: list[tuple[str, str]] = [
    ("date", "Date"),
    ("today_date", "Today date"),
    ("prayer", "Prayer"),
    ("pastor", "Pastor"),
    ("benediction", "Benediction"),
    ("fellowship", "Fellowship"),
    ("responsive", "Responsive reading"),
    ("hymn1", "Hymn 1"),
    ("hymn2", "Hymn 2"),
    ("scripture", "Scripture"),
    ("sermon_title", "Sermon title"),
    ("sermon_title2", "Youth Sermon"),
    ("sermon_part1", "Sermon part 1"),
    ("sermon_part1_desc", "Sermon part 1 desc"),
    ("sermon_part2", "Sermon part 2"),
    ("sermon_part2_desc", "Sermon part 2 desc"),
    ("sermon_part3", "Sermon part 3"),
    ("sermon_part3_desc", "Sermon part 3 desc"),
]


@dataclass
class GenerateOptions:
    template: Path = DEFAULT_TEMPLATE
    thumbnail_template: Path = DEFAULT_THUMBNAIL_TEMPLATE
    output: Path | None = None
    output_dir: Path = DEFAULT_OUTPUT_DIR
    translate: bool = True
    insert_responsive: bool = True
    insert_scripture: bool = True
    insert_sermon_verses: bool = True
    insert_hymns: bool = True
    generate_thumbnail: bool = True
    hymns_dir: Path = DEFAULT_HYMNS_DIR
    hymn_background_image: Path | None = None
    save_json: Path | None = None
    on_progress: Callable[[str], None] | None = None


def _report_progress(opts: GenerateOptions, message: str) -> None:
    if opts.on_progress is not None:
        opts.on_progress(message)


@dataclass
class GenerateResult:
    output_path: Path
    data: dict[str, Any]
    replaced_count: int
    translated_fields: list[str] = field(default_factory=list)
    remaining_tokens: list[str] = field(default_factory=list)
    hymn_stats: dict[str, Any] | None = None
    responsive_stats: dict[str, Any] | None = None
    scripture_stats: dict[str, Any] | None = None
    sermon_verse_stats: dict[str, int] | None = None
    youth_sermon_stats: dict[str, Any] | None = None
    thumbnail_path: Path | None = None
    thumbnail_replaced_count: int = 0
    thumbnail_remaining_tokens: list[str] = field(default_factory=list)
    saved_json: Path | None = None


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def build_output_path(data: dict[str, Any], output_dir: Path) -> Path:
    date_value = str(data.get("date", "")).strip()
    if date_value:
        return output_dir / f"{date_value}_주일예배.pptx"
    return output_dir / "주일예배.pptx"


def build_thumbnail_output_path(data: dict[str, Any], output_dir: Path) -> Path:
    date_value = str(data.get("date", "")).strip()
    if date_value:
        return output_dir / f"{date_value}_thumbnail.pptx"
    return output_dir / "thumbnail.pptx"


def discover_pdf(directory: Path) -> Path | None:
    pdfs = sorted(directory.glob("*.pdf"))
    return pdfs[0] if pdfs else None


def load_week_data(
    *,
    from_pdf: bool = False,
    bulletin_pdf: Path | str | None = None,
    sermon_pdf: Path | str | None = None,
    has_youth_sermon: bool = False,
    json_path: Path | str | None = None,
    input_dir: Path | str = DEFAULT_INPUT_DIR,
    input2_dir: Path | str = DEFAULT_INPUT2_DIR,
) -> dict[str, Any]:
    """Load weekly data from PDFs and/or JSON."""
    data: dict[str, Any] = {}

    if from_pdf:
        data = parse_week_from_pdfs(
            bulletin_pdf=bulletin_pdf,
            sermon_pdf=sermon_pdf,
            has_youth_sermon=has_youth_sermon,
            input_dir=input_dir,
            input2_dir=input2_dir,
        )

    if json_path:
        json_file = Path(json_path)
        if not json_file.exists():
            raise FileNotFoundError(f"JSON file not found: {json_file}")
        if data:
            data = merge_week_data(data, load_json(json_file))
        else:
            data = load_json(json_file)

    if not data:
        raise ValueError("No weekly data source provided.")

    return enrich_responsive_data(
        enrich_sermon_part_verses(
            normalize_week_sermon_text(apply_scripture_range_to_data(data))
        )
    )


def generate_week_ppt(
    data: dict[str, Any],
    options: GenerateOptions | None = None,
) -> GenerateResult:
    """Validate data, replace placeholders, optionally insert hymns."""
    opts = options or GenerateOptions()

    if not opts.template.exists():
        raise FileNotFoundError(
            f"Template not found: {opts.template}. "
            "Run: python scripts/create_sample_template.py"
        )

    if opts.generate_thumbnail and not opts.thumbnail_template.exists():
        raise FileNotFoundError(
            f"Thumbnail template not found: {opts.thumbnail_template}. "
            "Place Thumbnail_Template.pptx in templates/."
        )

    missing = validate_required_fields(data)
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    _report_progress(opts, "데이터 검증 완료")

    saved_json: Path | None = None
    if opts.save_json:
        _report_progress(opts, "주보 JSON 저장 중...")
        save_payload = apply_scripture_range_to_data(data)
        save_payload["scripture_verses"] = build_scripture_verses(save_payload)
        save_payload["responsive_lines"] = build_responsive_lines(
            save_payload,
            translate=opts.translate,
        )
        save_json(opts.save_json, save_payload)
        saved_json = opts.save_json
        _report_progress(opts, f"JSON 저장 완료: {opts.save_json.name}")

    output_path = opts.output or build_output_path(data, opts.output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _report_progress(opts, "템플릿 placeholder 치환 중...")
    replaced_count, remaining_tokens, translated_fields = apply_weekly_data(
        template_path=str(opts.template),
        output_path=str(output_path),
        data=data,
        translate=opts.translate,
    )
    _report_progress(opts, f"placeholder 치환 완료 ({replaced_count}개)")

    background_path = opts.hymn_background_image
    if background_path and not Path(background_path).is_file():
        background_path = None

    fixed_background_stats: dict[str, Any] | None = None
    youth_sermon_stats = None
    sermon_verse_stats = None
    responsive_stats = None
    scripture_stats = None
    hymn_stats: dict[str, Any] | None = None

    if needs_powerpoint_session(opts, data, background_path=background_path):
        _report_progress(
            opts,
            "PowerPoint 실행 중... (COM 작업 시작, 10~30초 걸릴 수 있습니다)",
        )
        with powerpoint_edit_session(output_path) as presentation:
            _report_progress(opts, "PowerPoint 연결 완료")

            if background_path:
                _report_progress(opts, "찬송 배경 슬라이드(34-36) 배경 적용 중...")
                fixed_background_stats = apply_fixed_worship_backgrounds_only(
                    output_path,
                    background_path,
                    presentation=presentation,
                )
                _report_progress(
                    opts,
                    f"찬송 배경 적용 완료 ({fixed_background_stats.get('fixed_background_slides', 0)} slides)",
                )

            _report_progress(opts, "Youth Sermon 슬라이드 확인 중...")
            youth_sermon_stats = apply_youth_sermon_slide(
                output_path,
                data,
                presentation=presentation,
            )
            if youth_sermon_stats and youth_sermon_stats.get("youth_sermon_slide") == "deleted":
                remaining_tokens.discard("{{SERMON_TITLE2}}")
                _report_progress(opts, "Youth Sermon 슬라이드 삭제")
            elif youth_sermon_stats:
                _report_progress(opts, "Youth Sermon 슬라이드 유지")

            if opts.insert_sermon_verses:
                _report_progress(opts, "설교 파트 구절 삽입 중...")
                sermon_verse_stats = apply_sermon_part_verses(
                    output_path,
                    data,
                    presentation=presentation,
                )
                if sermon_verse_stats and sermon_verse_stats.get("filled"):
                    for token, field in SERMON_VERSE_TOKEN_FIELDS:
                        if str(data.get(field, "")).strip():
                            remaining_tokens.discard(token)
                    _report_progress(
                        opts,
                        f"설교 파트 구절 완료 ({sermon_verse_stats.get('filled', 0)}개)",
                    )

            if opts.insert_responsive:
                _report_progress(opts, "교독문 슬라이드 생성 중...")
                prepared = dict(data)
                prepared["responsive_lines"] = build_responsive_lines(
                    prepared,
                    translate=opts.translate,
                )
                responsive_stats = insert_responsive_reading(
                    output_path,
                    prepared,
                    translate=opts.translate,
                    presentation=presentation,
                )
                if responsive_stats:
                    _report_progress(
                        opts,
                        f"교독문 슬라이드 완료 ({responsive_stats.get('responsive_slides', 0)} slides)",
                    )

            if opts.insert_scripture:
                _report_progress(opts, "성경 구절 슬라이드 생성 중...")
                prepared = apply_scripture_range_to_data(data)
                prepared["scripture_verses"] = build_scripture_verses(prepared)
                scripture_stats = insert_scripture_verses(
                    output_path,
                    prepared,
                    presentation=presentation,
                )
                if scripture_stats:
                    _report_progress(
                        opts,
                        f"성경 구절 슬라이드 완료 ({scripture_stats.get('verse_slides', 0)} slides)",
                    )

            if opts.insert_hymns:
                _report_progress(opts, "찬송가 슬라이드 삽입 중...")
                hymn_stats = insert_hymns(
                    output_path,
                    data,
                    opts.hymns_dir,
                    background_image=background_path,
                    presentation=presentation,
                )
                if hymn_stats:
                    _report_progress(
                        opts,
                        "찬송가 삽입 완료: "
                        f"{hymn_stats.get('hymn1_file')} ({hymn_stats.get('hymn1')} slides), "
                        f"{hymn_stats.get('hymn2_file')} ({hymn_stats.get('hymn2')} slides)",
                    )

            _report_progress(opts, "PowerPoint 저장 중...")
    else:
        youth_sermon_stats = apply_youth_sermon_slide(output_path, data)

    if fixed_background_stats:
        if hymn_stats is None:
            hymn_stats = fixed_background_stats
        else:
            hymn_stats = {**fixed_background_stats, **hymn_stats}

    thumbnail_path: Path | None = None
    thumbnail_replaced_count = 0
    thumbnail_remaining_tokens: set[str] = set()
    if opts.generate_thumbnail:
        _report_progress(opts, "썸네일 PPT 생성 중...")
        thumbnail_path = build_thumbnail_output_path(data, output_path.parent)
        thumbnail_replaced_count, thumbnail_remaining_tokens = generate_thumbnail_ppt(
            template_path=opts.thumbnail_template,
            output_path=thumbnail_path,
            data=data,
        )
        _report_progress(opts, f"썸네일 PPT 완료: {thumbnail_path.name}")

    _report_progress(opts, f"생성 완료: {output_path.name}")

    return GenerateResult(
        output_path=output_path,
        data=data,
        replaced_count=replaced_count,
        translated_fields=translated_fields,
        remaining_tokens=sorted(remaining_tokens),
        hymn_stats=hymn_stats,
        responsive_stats=responsive_stats,
        scripture_stats=scripture_stats,
        sermon_verse_stats=sermon_verse_stats,
        youth_sermon_stats=youth_sermon_stats,
        thumbnail_path=thumbnail_path,
        thumbnail_replaced_count=thumbnail_replaced_count,
        thumbnail_remaining_tokens=sorted(thumbnail_remaining_tokens),
        saved_json=saved_json,
    )


def parse_from_pdfs(
    bulletin_pdf: Path | str | None = None,
    sermon_pdf: Path | str | None = None,
    *,
    has_youth_sermon: bool = False,
) -> dict[str, Any]:
    """Convenience wrapper used by the GUI."""
    return load_week_data(
        from_pdf=True,
        bulletin_pdf=bulletin_pdf,
        sermon_pdf=sermon_pdf,
        has_youth_sermon=has_youth_sermon,
    )
