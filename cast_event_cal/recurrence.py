from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
RESOLVER_VERSION = "recurrence-v1"

_WEEKDAY = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
_CLOCK_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*(?::|：|時)\s*([0-5]?\d)?\s*分?")
_ORDINAL_RE = re.compile(r"第\s*([1-5](?:\s*[・,、]\s*[1-5])*)\s*(月|火|水|木|金|土|日)曜(?:日)?")
_WEEKLY_RE = re.compile(r"毎週\s*(月|火|水|木|金|土|日)曜(?:日)?")
_MONTHLY_RE = re.compile(r"毎月[^\n]{0,24}?第\s*([1-5](?:\s*[・,、]\s*[1-5])*)\s*(月|火|水|木|金|土|日)曜(?:日)?")


@dataclass(frozen=True)
class RecurrenceRule:
    frequency: str
    weekdays: tuple[int, ...]
    ordinals: tuple[int, ...]
    local_time: time
    timezone: str = "Asia/Tokyo"

    def as_dict(self) -> dict[str, Any]:
        return {
            "frequency": self.frequency,
            "weekdays": list(self.weekdays),
            "ordinals": list(self.ordinals),
            "local_time": self.local_time.strftime("%H:%M"),
            "timezone": self.timezone,
            "resolver_version": RESOLVER_VERSION,
        }


def parse_recurrence(text: str) -> RecurrenceRule | None:
    clock = _CLOCK_RE.search(text)
    if not clock:
        return None
    local_time = time(int(clock.group(1)), int(clock.group(2) or 0))

    monthly = _MONTHLY_RE.search(text)
    if monthly:
        ordinals = tuple(int(v) for v in re.split(r"\s*[・,、]\s*", monthly.group(1)))
        return RecurrenceRule("monthly_ordinal", (_WEEKDAY[monthly.group(2)],), ordinals, local_time)

    weekly = _WEEKLY_RE.search(text)
    if weekly:
        return RecurrenceRule("weekly", (_WEEKDAY[weekly.group(1)],), (), local_time)

    ordinal = _ORDINAL_RE.search(text)
    if ordinal:
        ordinals = tuple(int(v) for v in re.split(r"\s*[・,、]\s*", ordinal.group(1)))
        return RecurrenceRule("monthly_ordinal", (_WEEKDAY[ordinal.group(2)],), ordinals, local_time)
    return None


def _nth_weekday(year: int, month: int, weekday: int, ordinal: int) -> date | None:
    first_weekday, days = calendar.monthrange(year, month)
    day = 1 + (weekday - first_weekday) % 7 + 7 * (ordinal - 1)
    return date(year, month, day) if day <= days else None


def materialize_next(rule: RecurrenceRule, *, after: datetime, count: int = 1) -> list[datetime]:
    if count < 1:
        return []
    local_after = after.astimezone(JST)
    out: list[datetime] = []
    if rule.frequency == "weekly":
        cursor = local_after.date()
        while len(out) < count:
            delta = (rule.weekdays[0] - cursor.weekday()) % 7
            candidate_date = cursor + timedelta(days=delta)
            candidate = datetime.combine(candidate_date, rule.local_time, JST)
            if candidate <= local_after:
                cursor = candidate_date + timedelta(days=1)
                continue
            out.append(candidate)
            cursor = candidate_date + timedelta(days=1)
        return out

    year, month = local_after.year, local_after.month
    while len(out) < count:
        month_candidates: list[datetime] = []
        for ordinal in rule.ordinals:
            candidate_date = _nth_weekday(year, month, rule.weekdays[0], ordinal)
            if candidate_date is None:
                continue
            candidate = datetime.combine(candidate_date, rule.local_time, JST)
            if candidate > local_after:
                month_candidates.append(candidate)
        for candidate in sorted(month_candidates):
            out.append(candidate)
            if len(out) == count:
                return out
        month += 1
        if month == 13:
            year += 1
            month = 1
    return out


def resolve_recurrence(text: str, *, after: datetime, count: int = 1) -> dict[str, Any]:
    rule = parse_recurrence(text)
    if rule is None:
        return {"status": "unresolved", "reason": "incomplete_or_unsupported_recurrence", "resolver_version": RESOLVER_VERSION}
    occurrences = materialize_next(rule, after=after, count=count)
    return {
        "status": "resolved",
        "rule": rule.as_dict(),
        "occurrences": [value.isoformat() for value in occurrences],
        "resolver_version": RESOLVER_VERSION,
    }
