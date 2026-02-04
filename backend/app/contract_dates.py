from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable


@dataclass(frozen=True)
class DateSpan:
    start: date
    end: date
    kind: str  # "date" | "range"
    source: str


_DATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b"),
    re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b"),
]

_RANGE_PATTERNS: list[re.Pattern[str]] = [
    # с 01.02.2026 по 10.02.2026 / до 10.02.2026
    re.compile(
        r"(?:(?:с|со)\s*)"
        r"(?P<a>\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})"
        r"\s*(?:по|до)\s*"
        r"(?P<b>\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})",
        flags=re.IGNORECASE,
    ),
    # 01.02.2026 - 10.02.2026
    re.compile(
        r"(?P<a>\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})"
        r"\s*[\-–—]\s*"
        r"(?P<b>\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})"
    ),
]


def extract_date_spans(text: str, *, max_items: int = 20) -> list[DateSpan]:
    text = text or ""

    spans: list[DateSpan] = []

    # 1) Extract ranges first
    for pat in _RANGE_PATTERNS:
        for m in pat.finditer(text):
            a = _parse_date(m.group("a"))
            b = _parse_date(m.group("b"))
            if not a or not b:
                continue
            start, end = (a, b) if a <= b else (b, a)
            spans.append(DateSpan(start=start, end=end, kind="range", source=m.group(0)))
            if len(spans) >= max_items:
                return spans

    # 2) Extract single dates, skipping ones that are inside already captured range source strings
    # This is a heuristic to reduce duplicates.
    range_sources = "\n".join(s.source for s in spans)
    for d in _iter_dates(text):
        if d in range_sources:
            continue
        parsed = _parse_date(d)
        if not parsed:
            continue
        spans.append(DateSpan(start=parsed, end=parsed, kind="date", source=d))
        if len(spans) >= max_items:
            break

    # Deduplicate
    uniq: dict[tuple[date, date], DateSpan] = {}
    for s in spans:
        key = (s.start, s.end)
        if key not in uniq:
            uniq[key] = s
    return list(uniq.values())


def _iter_dates(text: str) -> Iterable[str]:
    for pat in _DATE_PATTERNS:
        for m in pat.finditer(text):
            yield m.group(0)


def _parse_date(s: str) -> date | None:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None
