"""Extract weekly worship data from bulletin and sermon PDF files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz

from app_paths import get_app_root
from bible_fetcher import enrich_scripture_data, enrich_sermon_part_verses
from responsive_library import enrich_responsive_data
from korean_text import format_sermon_part_desc, format_sermon_part_title
from sermon_verse_parser import parse_sermon_outline, parse_sermon_part_verses

ROOT = get_app_root()
DEFAULT_INPUT_DIR = ROOT / "input"
DEFAULT_INPUT2_DIR = ROOT / "input2"

# Collapse whitespace for regex matching on bulletin labels (e.g. "성 경 봉 독").
_WS = r"\s*"


def find_pdf(directory: Path, label: str) -> Path:
    """Return the only PDF in a folder, or the first when several exist."""
    pdfs = sorted(directory.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDF found in {directory} ({label})")
    return pdfs[0]


def _page_halves(page: fitz.Page) -> tuple[fitz.Rect, fitz.Rect]:
    rect = page.rect
    mid_x = rect.width / 2
    left = fitz.Rect(0, 0, mid_x, rect.height)
    right = fitz.Rect(mid_x, 0, rect.width, rect.height)
    return left, right


def _half_text(page: fitz.Page, side: str) -> str:
    left, right = _page_halves(page)
    clip = left if side == "left" else right
    return page.get_text("text", clip=clip)


def _parse_bulletin_dates(text: str) -> tuple[str | None, str | None]:
    """Return ISO date and bulletin display date (e.g. 6.7.2026) from text."""
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if not match:
        return None, None

    month, day, year = match.groups()
    iso_date = f"{year}-{int(month):02d}-{int(day):02d}"
    display_date = f"{int(month)}.{int(day)}.{year}"
    return iso_date, display_date


def _parse_bulletin_date(text: str) -> str | None:
    iso_date, _display_date = _parse_bulletin_dates(text)
    return iso_date


def _trim_service_tail(text: str) -> str:
    """Keep only the first worship-order block (before the next service date)."""
    match = re.search(
        r"\d{1,2}\.\d{1,2}\.\d{4}.{0,40}?(?:오후|pm|PM)",
        text,
        flags=re.DOTALL,
    )
    if match:
        return text[: match.start()]
    return text


def _clean_person_line(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    cleaned = re.sub(r"\s*(인\s*도\s*자|다\s*같\s*이).*$", "", cleaned)
    return cleaned.strip()


def _format_hymn(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    return f"{digits}장" if digits else number.strip()


def _format_responsive(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    return f"{digits}번" if digits else number.strip()


_PERSON_TITLE = r"(?:목사|전도사|장로|집사|권사|강도사|교역자|성도)"


def _parse_sermon_pastor(text: str) -> str | None:
    """Extract the preacher name shown after the main sermon title in the left column."""
    marker = re.search(rf"설{_WS}교", text)
    if not marker:
        return None

    for line in text[marker.end() :].splitlines():
        cleaned = _clean_person_line(line)
        if not cleaned:
            continue
        if cleaned.startswith("*") or re.search(rf"헌{_WS}금", cleaned):
            break
        if re.search(rf"교{_WS}회{_WS}소{_WS}식", cleaned):
            break
        if re.search(_PERSON_TITLE, cleaned):
            return cleaned
        if re.search(r"[「\"“'""]", cleaned):
            continue
    return None


def _parse_benediction(text: str) -> str | None:
    """Extract the person leading benediction (축도) from a worship-order block."""
    matches = list(
        re.finditer(rf"\*?{_WS}축{_WS}도{_WS}([^\n]+)", text),
    )
    if not matches:
        return None

    cleaned = _clean_person_line(matches[-1].group(1))
    return cleaned or None


def _parse_youth_sermon(text: str) -> str | None:
    """Extract Youth Sermon title from bulletin PDF text."""
    patterns = (
        rf"Youth{_WS}Sermon{_WS}\n\s*[「\"“]\s*([^\"”\n]+)\s*[\"”」]",
        rf"Youth{_WS}Sermon{_WS}\n\s*([^\n]+)",
        rf"Youth{_WS}Sermon{_WS}:\s*([^\n]+)",
        rf"Youth{_WS}Sermon{_WS}[「\"“]\s*([^\"”\n]+)\s*[\"”」]",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        title = match.group(1).strip().strip("\"”」")
        title = re.sub(r"\s*(인\s*도\s*자|다\s*같\s*이).*$", "", title).strip()
        if title:
            return title
    return None


def _parse_hymn1_before_prayer(text: str) -> str | None:
    """Return the last opening hymn number before the representative prayer block."""
    prayer_match = re.search(rf"대{_WS}표{_WS}기{_WS}도", text)
    prefix = text[: prayer_match.start()] if prayer_match else text
    hymn_number: str | None = None
    for match in re.finditer(rf"(?<!\*)찬{_WS}송{_WS}(\d+){_WS}장", prefix):
        hymn_number = match.group(1)
    if hymn_number:
        return _format_hymn(hymn_number)
    return None


def _parse_left_column_bulletin_fields(
    left_text: str,
    *,
    include_youth_sermon: bool = False,
) -> dict[str, Any]:
    """Parse the 11am worship order from the left bulletin column."""
    result: dict[str, Any] = {}

    hymn1 = _parse_hymn1_before_prayer(left_text)
    if hymn1:
        result["hymn1"] = hymn1

    responsive_match = re.search(
        rf"교{_WS}독{_WS}문{_WS}(\d+){_WS}번",
        left_text,
    )
    if responsive_match:
        result["responsive"] = _format_responsive(responsive_match.group(1))

    prayer_match = re.search(
        rf"대{_WS}표{_WS}기{_WS}도{_WS}([^\n]+)",
        left_text,
    )
    if prayer_match:
        prayer = _clean_person_line(prayer_match.group(1))
        if prayer:
            result["prayer"] = prayer

    if include_youth_sermon:
        youth_sermon = _parse_youth_sermon(left_text)
        if youth_sermon:
            result["sermon_title2"] = youth_sermon

    scripture_match = re.search(
        rf"성{_WS}경{_WS}봉{_WS}독{_WS}([^\n]+)",
        left_text,
    )
    if scripture_match:
        scripture = _clean_person_line(scripture_match.group(1))
        if scripture:
            result["scripture"] = scripture

    sermon_match = re.search(
        rf"설{_WS}교{_WS}[「\"“]?\s*([^\"”\n]+)[\"”]?",
        left_text,
    )
    if sermon_match:
        result["sermon_title"] = sermon_match.group(1).strip()

    hymn2_match = re.search(rf"\*{_WS}찬{_WS}송{_WS}(\d+){_WS}장", left_text)
    if hymn2_match:
        result["hymn2"] = _format_hymn(hymn2_match.group(1))

    pastor = _parse_sermon_pastor(left_text)
    if pastor:
        result["pastor"] = pastor

    benediction = _parse_benediction(left_text)
    if benediction:
        result["benediction"] = benediction

    return result


def _parse_fellowship(text: str) -> str | None:
    """Extract today's fellowship host from bulletin page 2."""
    match = re.search(
        rf"오{_WS}늘{_WS}의{_WS}친{_WS}교\s*[:=]\s*([^\n]+)",
        text,
    )
    if not match:
        return None

    name = _clean_person_line(match.group(1))
    name = re.sub(r"\s*친교\s*후.*$", "", name).strip()
    return name or None


def parse_bulletin_page2(path: Path | str) -> dict[str, Any]:
    """Parse bulletin page 2 for fellowship and other announcements."""
    doc = fitz.open(path)
    if doc.page_count < 2:
        doc.close()
        return {}

    text = doc[1].get_text("text")
    doc.close()

    result: dict[str, Any] = {}
    fellowship = _parse_fellowship(text)
    if fellowship:
        result["fellowship"] = fellowship
    return result


def parse_bulletin(
    path: Path | str,
    *,
    has_youth_sermon: bool = False,
) -> dict[str, Any]:
    """Parse bulletin PDF pages 1-2."""
    result = parse_bulletin_page1(path, has_youth_sermon=has_youth_sermon)
    result.update(parse_bulletin_page2(path))
    return result


def parse_bulletin_page1(
    path: Path | str,
    *,
    has_youth_sermon: bool = False,
) -> dict[str, Any]:
    """Parse bulletin page 1 from the left (11am) column."""
    doc = fitz.open(path)
    if doc.page_count < 1:
        doc.close()
        raise ValueError(f"Bulletin PDF has no pages: {path}")

    page = doc[0]
    page_rect = page.rect
    top_left = fitz.Rect(0, 0, page_rect.width / 2, page_rect.height * 0.15)
    top_left_text = page.get_text("text", clip=top_left)
    left_text = _trim_service_tail(_half_text(page, "left"))
    right_text = _trim_service_tail(_half_text(page, "right"))
    doc.close()

    result: dict[str, Any] = {}

    date_value = None
    today_date = None
    for source in (top_left_text, left_text, right_text):
        iso_date, display_date = _parse_bulletin_dates(source)
        if iso_date:
            date_value = iso_date
            today_date = display_date
            break

    if date_value:
        result["date"] = date_value
    if today_date:
        result["today_date"] = today_date

    result.update(
        _parse_left_column_bulletin_fields(
            left_text,
            include_youth_sermon=has_youth_sermon,
        )
    )

    return result


def parse_sermon_pdf(path: Path | str) -> dict[str, Any]:
    """Parse sermon notes PDF for title, outline parts, and part verse quotes."""
    doc = fitz.open(path)
    if doc.page_count < 1:
        doc.close()
        raise ValueError(f"Sermon PDF has no pages: {path}")

    page_count = min(doc.page_count, 3)
    text = "\n".join(doc[i].get_text("text") for i in range(page_count))
    doc.close()

    result: dict[str, Any] = {}

    title_match = re.search(r"제목\s*:\s*(.+)", text)
    if title_match:
        result["sermon_title"] = title_match.group(1).strip()

    scripture_match = re.search(r"성\s*경\s*:\s*(.+)", text)
    if scripture_match:
        result["scripture"] = scripture_match.group(1).strip()

    for index, title, _verse, desc in parse_sermon_outline(text):
        result[f"sermon_part{index}"] = format_sermon_part_title(title)
        result[f"sermon_part{index}_desc"] = format_sermon_part_desc(desc)

    part_verses = parse_sermon_part_verses(text)
    if part_verses:
        result["_sermon_part_verses"] = part_verses

    return result


def parse_week_from_pdfs(
    bulletin_pdf: Path | str | None = None,
    sermon_pdf: Path | str | None = None,
    *,
    has_youth_sermon: bool = False,
    input_dir: Path | str = DEFAULT_INPUT_DIR,
    input2_dir: Path | str = DEFAULT_INPUT2_DIR,
) -> dict[str, Any]:
    """Merge bulletin and sermon PDF fields into weekly JSON data."""
    input_dir = Path(input_dir)
    input2_dir = Path(input2_dir)

    bulletin_path = Path(bulletin_pdf) if bulletin_pdf else find_pdf(input_dir, "bulletin")
    sermon_path = Path(sermon_pdf) if sermon_pdf else find_pdf(input2_dir, "sermon")

    if not bulletin_path.exists():
        raise FileNotFoundError(f"Bulletin PDF not found: {bulletin_path}")
    if not sermon_path.exists():
        raise FileNotFoundError(f"Sermon PDF not found: {sermon_path}")

    bulletin_data = parse_bulletin(bulletin_path, has_youth_sermon=has_youth_sermon)
    sermon_data = parse_sermon_pdf(sermon_path)

    data: dict[str, Any] = dict(bulletin_data)
    bulletin_priority = {
        key
        for key in ("sermon_title", "scripture", "hymn1", "hymn2", "prayer", "responsive", "pastor", "benediction")
        if bulletin_data.get(key)
    }
    for key, value in sermon_data.items():
        if key in bulletin_priority:
            continue
        data[key] = value

    return enrich_responsive_data(enrich_sermon_part_verses(enrich_scripture_data(data)))
