"""Korean Bible book abbreviations and English reference formatting."""

from __future__ import annotations

import re

from dataclasses import dataclass

from scripture_parser import ScriptureRange, parse_scripture_range


@dataclass(frozen=True)
class BibleBook:
    english_name: str
    bskorea_code: str
    aliases: tuple[str, ...]


BOOKS: tuple[BibleBook, ...] = (
    BibleBook("Genesis", "gen", ("창", "창세", "창세기")),
    BibleBook("Exodus", "exo", ("출", "출애", "출애굽", "출애굽기")),
    BibleBook("Leviticus", "lev", ("레", "레위", "레위기")),
    BibleBook("Numbers", "num", ("민", "민수", "민수기")),
    BibleBook("Deuteronomy", "deu", ("신", "신명", "신명기")),
    BibleBook("Joshua", "jos", ("수", "여호", "여호수아")),
    BibleBook("Judges", "jdg", ("삿", "판관", "사사", "사사기")),
    BibleBook("Ruth", "rut", ("룻", "룻기")),
    BibleBook("1 Samuel", "1sa", ("삼상", "사무엘상")),
    BibleBook("2 Samuel", "2sa", ("삼하", "사무엘하")),
    BibleBook("1 Kings", "1ki", ("왕상", "열왕기상")),
    BibleBook("2 Kings", "2ki", ("왕하", "열왕기하")),
    BibleBook("1 Chronicles", "1ch", ("대상", "역대상")),
    BibleBook("2 Chronicles", "2ch", ("대하", "역대하")),
    BibleBook("Ezra", "ezr", ("스", "에스", "에스라")),
    BibleBook("Nehemiah", "neh", ("느", "느헤", "느헤미야")),
    BibleBook("Esther", "est", ("에", "에스더")),
    BibleBook("Job", "job", ("욥", "욥기")),
    BibleBook("Psalms", "psa", ("시", "시편")),
    BibleBook("Proverbs", "pro", ("잠", "잠언")),
    BibleBook("Ecclesiastes", "ecc", ("전", "전도", "전도서")),
    BibleBook("Song of Solomon", "sng", ("아", "아가", "아가서")),
    BibleBook("Isaiah", "isa", ("사", "이사", "이사야")),
    BibleBook("Jeremiah", "jer", ("렘", "예레", "예레미야")),
    BibleBook("Lamentations", "lam", ("애", "애가")),
    BibleBook("Ezekiel", "ezk", ("겔", "에스", "에스겔")),
    BibleBook("Daniel", "dan", ("단", "다니", "다니엘")),
    BibleBook("Hosea", "hos", ("호", "호세", "호세아")),
    BibleBook("Joel", "jol", ("욜", "요엘")),
    BibleBook("Amos", "amo", ("암", "아모", "아모스")),
    BibleBook("Obadiah", "oba", ("옵", "오바", "오바댜")),
    BibleBook("Jonah", "jnh", ("욘", "요나")),
    BibleBook("Micah", "mic", ("미", "미가")),
    BibleBook("Nahum", "nam", ("나", "나훔")),
    BibleBook("Habakkuk", "hab", ("합", "하박", "하박국")),
    BibleBook("Zephaniah", "zep", ("습", "스바", "스바냐")),
    BibleBook("Haggai", "hag", ("학", "학개")),
    BibleBook("Zechariah", "zec", ("슥", "스가", "스가랴")),
    BibleBook("Malachi", "mal", ("말", "말라", "말라기")),
    BibleBook("Matthew", "mat", ("마", "마태", "마태복음")),
    BibleBook("Mark", "mrk", ("막", "마가", "마가복음")),
    BibleBook("Luke", "luk", ("눅", "누가", "누가복음")),
    BibleBook("John", "jhn", ("요", "요한", "요한복음")),
    BibleBook("Acts", "act", ("행", "사도", "사도행전")),
    BibleBook("Romans", "rom", ("롬", "로마", "로마서")),
    BibleBook("1 Corinthians", "1co", ("고전", "고린도전서")),
    BibleBook("2 Corinthians", "2co", ("고후", "고린도후서")),
    BibleBook("Galatians", "gal", ("갈", "갈라", "갈라디아서")),
    BibleBook("Ephesians", "eph", ("엡", "에베", "에베소서")),
    BibleBook("Philippians", "php", ("빌", "빌립", "빌립보서")),
    BibleBook("Colossians", "col", ("골", "골로", "골로새서")),
    BibleBook("1 Thessalonians", "1th", ("살전", "데살로니가전서")),
    BibleBook("2 Thessalonians", "2th", ("살후", "데살로니가후서")),
    BibleBook("1 Timothy", "1ti", ("딤전", "디모데전서")),
    BibleBook("2 Timothy", "2ti", ("딤후", "디모데후서")),
    BibleBook("Titus", "tit", ("딛", "디도", "디도서")),
    BibleBook("Philemon", "phm", ("몬", "빌레", "빌레몬서")),
    BibleBook("Hebrews", "heb", ("히", "히브", "히브리서")),
    BibleBook("James", "jas", ("약", "야고", "야고보서")),
    BibleBook("1 Peter", "1pe", ("벧전", "베드로전서")),
    BibleBook("2 Peter", "2pe", ("벧후", "베드로후서")),
    BibleBook("1 John", "1jn", ("요일", "요한1서", "요한일서")),
    BibleBook("2 John", "2jn", ("요이", "요한2서", "요한이서")),
    BibleBook("3 John", "3jn", ("요삼", "요한3서", "요한삼서")),
    BibleBook("Jude", "jud", ("유", "유다", "유다서")),
    BibleBook("Revelation", "rev", ("계", "요계", "요한계시록", "계시록")),
)

_ALIAS_LOOKUP: dict[str, BibleBook] = {}
for book in BOOKS:
    for alias in book.aliases:
        _ALIAS_LOOKUP[alias] = book
    _ALIAS_LOOKUP[book.english_name.lower()] = book
    _ALIAS_LOOKUP[book.bskorea_code] = book


def resolve_bible_book(scripture: str, parsed: ScriptureRange | None = None) -> BibleBook | None:
    """Resolve a Korean or English book prefix from a scripture reference string."""
    cleaned = scripture.strip()
    if parsed and parsed.book:
        book_key = parsed.book.strip()
        if book_key in _ALIAS_LOOKUP:
            return _ALIAS_LOOKUP[book_key]
        for alias, book in _ALIAS_LOOKUP.items():
            if book_key.startswith(alias) or alias.startswith(book_key):
                return book

    for alias in sorted(_ALIAS_LOOKUP.keys(), key=len, reverse=True):
        if cleaned.startswith(alias):
            return _ALIAS_LOOKUP[alias]
    return None


def get_korean_book_full_name(book: BibleBook) -> str:
    """Return the longest Korean alias, e.g. '수' -> '여호수아'."""
    return max(book.aliases, key=len)


def format_scripture_reference_ko(scripture: str) -> str:
    """Normalize bulletin references like '수 14:6-15' to '수14:6-15'."""
    cleaned = scripture.strip()
    if not cleaned:
        return ""
    return re.sub(r"\s+", "", cleaned)


def format_scripture_reference_ko_full(scripture: str) -> str:
    """Convert '수17:15-30' to '여호수아 17:15-30'."""
    cleaned = format_scripture_reference_ko(scripture)
    if not cleaned:
        return ""

    parsed = parse_scripture_range(cleaned)
    if not parsed:
        return cleaned

    book = resolve_bible_book(cleaned, parsed)
    if book:
        book_name = get_korean_book_full_name(book)
    elif parsed.book:
        book_name = parsed.book
    else:
        book_name = ""

    if parsed.start == parsed.end:
        reference = f"{parsed.chapter}:{parsed.start}"
    else:
        reference = f"{parsed.chapter}:{parsed.start}-{parsed.end}"

    if book_name:
        return f"{book_name} {reference}"
    return reference


def format_scripture_reference_en(scripture: str) -> str | None:
    """Convert references like '수14:6-15' to 'Joshua 14:6-15'."""
    parsed = parse_scripture_range(scripture)
    if not parsed:
        return None

    book = resolve_bible_book(scripture, parsed)
    if not book:
        return None

    if parsed.start == parsed.end:
        return f"{book.english_name} {parsed.chapter}:{parsed.start}"
    return f"{book.english_name} {parsed.chapter}:{parsed.start}-{parsed.end}"
