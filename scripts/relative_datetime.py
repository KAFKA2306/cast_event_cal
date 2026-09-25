from __future__ import annotations

import re
from calendar import monthrange
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
FULLWIDTH_DIGIT_TRANSLATION = str.maketrans("０１２３４５６７８９", "0123456789")
EVIDENCE_SPAN_CHARS = 160
WEEKDAY_INDEX = {name: index for index, name in enumerate("月火水木金土日")}
CLOCK_CAPTURE_PATTERN = (
    r"(?P<period>午前|午後|(?<!今)夜)?\s*"
    r"(?P<hour>[01]?\d|2[0-3])"
    r"(?:[:：]\s*(?P<minute>[0-5]?\d)|時\s*(?:(?P<minute_jp>[0-5]?\d)\s*分?|(?P<half>半))?)"
)
NONTRIVIAL_CLOCK_RE = re.compile(
    r"(?:(?:午前|午後|(?<!今)夜)\s*(?:[01]?\d|2[0-3])\s*時|(?:[01]?\d|2[0-3])\s*時\s*半)"
)
WEEKDAY_PATTERN = re.compile(
    r"(?P<prefix>次(?:の)?|来週(?:の)?|今週(?:の)?)?\s*"
    r"(?P<weekday>[月火水木金土日])曜日?.{0,100}?" + CLOCK_CAPTURE_PATTERN,
    flags=re.IGNORECASE | re.DOTALL,
)
ORDINAL_RECURRING_WEEKDAY_PATTERN = re.compile(
    r"(?:毎月\s*)?第\s*\d+(?:\s*[、,・/]\s*第?\s*\d+)*\s*[月火水木金土日]曜(?:日)?",
    flags=re.IGNORECASE,
)
MULTI_WEEKLY_RECURRENCE_PATTERN = re.compile(
    r"毎週\s*(?P<weekdays>[月火水木金土日](?:曜(?:日)?)?"
    r"(?:\s*(?:[、,・/&]|と)\s*[月火水木金土日](?:曜(?:日)?)?)+)"
    r".{0,100}?" + CLOCK_CAPTURE_PATTERN,
    flags=re.IGNORECASE | re.DOTALL,
)
WEEKLY_RECURRENCE_PATTERN = re.compile(
    r"毎週\s*(?P<weekday>[月火水木金土日])(?:曜(?:日)?)?.{0,100}?"
    + CLOCK_CAPTURE_PATTERN,
    flags=re.IGNORECASE | re.DOTALL,
)
DAILY_RECURRENCE_PATTERN = re.compile(
    r"毎日.{0,100}?" + CLOCK_CAPTURE_PATTERN,
    flags=re.IGNORECASE | re.DOTALL,
)
MULTI_MONTHLY_DAY_RECURRENCE_PATTERN = re.compile(
    r"毎月\s*(?P<days>(?:3[01]|[12]?\d)日"
    r"(?:\s*(?:[、,・/&]|と)\s*(?:3[01]|[12]?\d)日)+)"
    r".{0,100}?" + CLOCK_CAPTURE_PATTERN,
    flags=re.IGNORECASE | re.DOTALL,
)
MONTHLY_DAY_RECURRENCE_PATTERN = re.compile(
    r"毎月\s*(?P<day>3[01]|[12]?\d)日.{0,100}?"
    + CLOCK_CAPTURE_PATTERN,
    flags=re.IGNORECASE | re.DOTALL,
)
LAST_WEEKDAY_MONTHLY_RECURRENCE_PATTERN = re.compile(
    r"毎月\s*(?:最終|最後の)\s*(?P<weekday>[月火水木金土日])曜(?:日)?"
    r".{0,100}?" + CLOCK_CAPTURE_PATTERN,
    flags=re.IGNORECASE | re.DOTALL,
)
ORDINAL_MONTHLY_RECURRENCE_PATTERN = re.compile(
    r"(?:毎月\s*)?第\s*(?P<ordinals>\d+(?:\s*[、,・/]\s*第?\s*\d+)*)\s*"
    r"(?P<weekday>[月火水木金土日])曜(?:日)?.{0,100}?"
    + CLOCK_CAPTURE_PATTERN,
    flags=re.IGNORECASE | re.DOTALL,
)
MULTI_EVENT_CLOCK_PATTERN = re.compile(
    r"(?:[01]?\d|2[0-3])時(?:半)?\s*からは.{0,240}?"
    r"(?:[01]?\d|2[0-3])時(?:半)?\s*からは",
    flags=re.IGNORECASE | re.DOTALL,
)
UNPREFIXED_WEEKDAY_PAST_CONTEXT_RE = re.compile(
    r"昨日|先日|参加してき|行ってき|営業してました",
    flags=re.IGNORECASE,
)
CLOCK_PATTERN = re.compile(CLOCK_CAPTURE_PATTERN)
RELATIVE_DAY_PATTERN = re.compile(r"本日|今日|明日|今夜|今晩|この後")
EXPLICIT_DATE_PATTERN = re.compile(
    r"(?<!\d)(?:20\d{2}\s*[./／⁄年-]\s*)?"
    r"(?:1[0-2]|0?[1-9])\s*(?:[./／⁄-]|\s*月\s*)\s*"
    r"(?:3[01]|[12]?\d)\s*日?(?!\d)"
)
DDMMYYYY_LABEL_PATTERN = re.compile(
    r"dd\s*[/／⁄]\s*mm\s*[/／⁄]\s*yyyy\s*[:：]\s*"
    r"(?P<day>3[01]|[12]?\d)\s*[/／⁄]\s*"
    r"(?P<month>1[0-2]|0?[1-9])\s*[/／⁄]\s*(?P<year>20\d{2})",
    flags=re.IGNORECASE,
)
RECOVERY_EVENT_RE = re.compile(
    r"集会|交流会|イベント|event|開催|営業|公演|ライブ|撮影会|演奏会|DJ|勉強会|祭|"
    r"参加|JOIN|リクイン|Group\s*[+＋]|グループインスタンス|request\s+invite",
    flags=re.IGNORECASE,
)
RECOVERY_ANNOUNCEMENT_RE = re.compile(
    r"告知|開催(?:します|いたします|予定|決定)?|OPEN|オープン|開場|開始|営業(?:します|予定)?",
    flags=re.IGNORECASE,
)
RECOVERY_ACCESS_RE = re.compile(
    r"join|ジョイン|リクイン|request\s*invite|フレンド申請|フレリク|"
    r"group\s*[+＋]|group\s*インスタンス|グループ(?:プラス|インスタンス)|"
    r"インスタンス|参加方法|参加希望|ご参加ください|参加してください|お越しください|"
    r"ご来場|ご来店",
    flags=re.IGNORECASE,
)
RECOVERY_PAST_RE = re.compile(
    r"参加してき|行ってき|楽しかった|昨日|先日|でした|してきました|"
    r"お邪魔(?:しました|してき)|ご参加ありがとうございました|"
    r"お越しいただきありがとうございました|見た後|観劇して|店休日でした|営業してました",
    flags=re.IGNORECASE,
)
RECOVERY_META_RE = re.compile(
    r"イベントNEWS|毎朝.{0,12}更新|告知.{0,20}(?:あります|出すとして)",
    flags=re.IGNORECASE | re.DOTALL,
)
RECOVERY_COMMERCE_RE = re.compile(
    r"販売|発売|セール|BOOTH|プレゼント|キャンペーン",
    flags=re.IGNORECASE,
)
RECOVERY_PHYSICAL_RE = re.compile(
    r"幕張メッセ|大阪|静岡|心斎橋|アメ村|居酒屋|リアル(?:で|会場|イベント)|一日店長",
    flags=re.IGNORECASE,
)
RECOVERY_BROADCAST_RE = re.compile(
    r"生配信|配信URL|配信はこちら|配信枠|配信\s*告知",
    flags=re.IGNORECASE,
)
RECOVERY_VIRTUAL_VENUE_RE = re.compile(
    r"(?:VRChat|VRC).{0,40}(?:会場|Group|インスタンス)|"
    r"(?:会場|Group|インスタンス).{0,40}(?:VRChat|VRC)",
    flags=re.IGNORECASE | re.DOTALL,
)
RECOVERY_WORLD_DESCRIPTION_RE = re.compile(
    r"World名|ワールド紹介|2019年から.{0,30}毎年開催",
    flags=re.IGNORECASE | re.DOTALL,
)
RECOVERY_VISIT_RE = re.compile(
    r"開催\s*中.{0,80}(?:に行く|見に行く)|(?:に行く|見に行く).{0,80}開催\s*中",
    flags=re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class DateResolution:
    event_at: datetime
    method: str
    anchor: datetime
    matched_text: str
    recurrence_rule: dict[str, Any] | None = None

    def evidence(self, utc_text: Callable[[datetime], str]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "method": self.method,
            "anchor": utc_text(self.anchor),
            "resolved_at": utc_text(self.event_at),
            "timezone": "Asia/Tokyo",
            "week_start": "monday",
            "matched_text": self.matched_text,
        }
        if self.recurrence_rule:
            payload["recurrence_rule"] = self.recurrence_rule
        return payload


def _jst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=JST)
    return value.astimezone(JST)



def _normalize_recovery_text(text: str) -> str:
    return (
        text.translate(FULLWIDTH_DIGIT_TRANSLATION)
        .replace("：", ":")
        .replace("／", "/")
        .replace("⁄", "/")
        .replace("．", ".")
        .replace("－", "-")
        .replace("〜", "~")
        .replace("～", "~")
    )


def _clock_parts(match: re.Match[str]) -> tuple[int, int] | None:
    hour = int(match.group("hour"))
    period = match.groupdict().get("period")
    if period == "午前":
        if hour == 12:
            hour = 0
        elif hour > 11:
            return None
    elif period == "午後":
        if hour < 12:
            hour += 12
        elif hour > 12:
            return None
    elif period == "夜":
        if hour == 12:
            return None
        if 1 <= hour <= 11:
            hour += 12
        else:
            return None

    minute = 30 if match.groupdict().get("half") else int(
        match.groupdict().get("minute")
        or match.groupdict().get("minute_jp")
        or 0
    )
    if minute > 59:
        return None
    return hour, minute


def _match_gap(left: re.Match[str], right: re.Match[str]) -> int:
    if left.end() <= right.start():
        return right.start() - left.end()
    if right.end() <= left.start():
        return left.start() - right.end()
    return 0


def _recovery_text_is_safe(text: str) -> bool:
    event = bool(RECOVERY_EVENT_RE.search(text))
    announcement = bool(RECOVERY_ANNOUNCEMENT_RE.search(text))
    access = bool(RECOVERY_ACCESS_RE.search(text))
    if not event or not (announcement or access):
        return False
    if RECOVERY_PAST_RE.search(text) or RECOVERY_META_RE.search(text):
        return False
    if RECOVERY_WORLD_DESCRIPTION_RE.search(text) or RECOVERY_VISIT_RE.search(text):
        return False
    if RECOVERY_COMMERCE_RE.search(text) and not access:
        return False
    if RECOVERY_PHYSICAL_RE.search(text) and not access:
        return False
    if (
        RECOVERY_BROADCAST_RE.search(text)
        and not access
        and not RECOVERY_VIRTUAL_VENUE_RE.search(text)
    ):
        return False
    return True


def _resolution_from_parts(
    *,
    year: int,
    month: int,
    day: int,
    clock: re.Match[str],
    anchor: datetime,
    method: str,
    matched_text: str,
) -> DateResolution | None:
    clock_parts = _clock_parts(clock)
    if clock_parts is None:
        return None
    hour, minute = clock_parts
    try:
        value = datetime(
            year,
            month,
            day,
            hour,
            minute,
            tzinfo=JST,
        )
    except ValueError:
        return None
    return DateResolution(
        event_at=value,
        method=method,
        anchor=anchor,
        matched_text=matched_text[:160],
    )


def _resolve_evidence_span_datetime(text: str, anchor: datetime) -> DateResolution | None:
    if not _recovery_text_is_safe(text):
        return None
    normalized = _normalize_recovery_text(text)
    clocks = list(CLOCK_PATTERN.finditer(normalized))
    if not clocks:
        return None

    choices: list[tuple[int, int, DateResolution]] = []

    for match in DDMMYYYY_LABEL_PATTERN.finditer(normalized):
        clock = min(clocks, key=lambda item: _match_gap(match, item))
        gap = _match_gap(match, clock)
        if gap > EVIDENCE_SPAN_CHARS:
            continue
        start = min(match.start(), clock.start())
        end = max(match.end(), clock.end())
        resolution = _resolution_from_parts(
            year=int(match.group("year")),
            month=int(match.group("month")),
            day=int(match.group("day")),
            clock=clock,
            anchor=anchor,
            method="explicit_ddmmyyyy_evidence_span",
            matched_text=normalized[start:end],
        )
        if resolution:
            choices.append((gap, 0, resolution))

    for match in EXPLICIT_DATE_PATTERN.finditer(normalized):
        token = match.group(0)
        parts = re.search(
            r"(?<!\d)(?:(?P<year>20\d{2})\s*[./年-]\s*)?"
            r"(?P<month>1[0-2]|0?[1-9])\s*(?:[./-]|\s*月\s*)\s*"
            r"(?P<day>3[01]|[12]?\d)(?!\d)",
            token,
        )
        if not parts:
            continue
        clock = min(clocks, key=lambda item: _match_gap(match, item))
        gap = _match_gap(match, clock)
        if gap > EVIDENCE_SPAN_CHARS:
            continue
        explicit_year = parts.group("year")
        year = int(explicit_year or anchor.year)
        month = int(parts.group("month"))
        day = int(parts.group("day"))
        start = min(match.start(), clock.start())
        end = max(match.end(), clock.end())
        resolution = _resolution_from_parts(
            year=year,
            month=month,
            day=day,
            clock=clock,
            anchor=anchor,
            method="explicit_calendar_date_evidence_span",
            matched_text=normalized[start:end],
        )
        if not resolution:
            continue
        if not explicit_year and resolution.event_at < anchor - timedelta(days=2):
            if anchor.month == 12 and month == 1:
                resolution = _resolution_from_parts(
                    year=anchor.year + 1,
                    month=month,
                    day=day,
                    clock=clock,
                    anchor=anchor,
                    method="explicit_calendar_date_evidence_span",
                    matched_text=normalized[start:end],
                )
            else:
                resolution = None
        if resolution:
            choices.append((gap, 1, resolution))

    for match in RELATIVE_DAY_PATTERN.finditer(normalized):
        clock = min(clocks, key=lambda item: _match_gap(match, item))
        gap = _match_gap(match, clock)
        if gap > EVIDENCE_SPAN_CHARS:
            continue
        day_offset = 1 if match.group(0) == "明日" else 0
        target = (anchor + timedelta(days=day_offset)).date()
        start = min(match.start(), clock.start())
        end = max(match.end(), clock.end())
        resolution = _resolution_from_parts(
            year=target.year,
            month=target.month,
            day=target.day,
            clock=clock,
            anchor=anchor,
            method="relative_day_evidence_span",
            matched_text=normalized[start:end],
        )
        if resolution:
            choices.append((gap, 2, resolution))

    if not choices:
        return None
    choices.sort(key=lambda item: (item[0], item[1], item[2].event_at))
    return choices[0][2]


def _recurrence_resolution(
    *,
    event_at: datetime,
    source_anchor: datetime,
    method: str,
    matched_text: str,
    recurrence_rule: dict[str, Any],
) -> DateResolution:
    return DateResolution(
        event_at=event_at,
        method=method,
        anchor=source_anchor,
        matched_text=matched_text[:160],
        recurrence_rule=recurrence_rule,
    )


def _monthly_candidates(
    *,
    after: datetime,
    days: list[int],
    hour: int,
    minute: int,
) -> list[datetime]:
    candidates: list[datetime] = []
    for offset in range(14):
        month_index = after.month - 1 + offset
        year = after.year + month_index // 12
        month = month_index % 12 + 1
        for day in days:
            if day > monthrange(year, month)[1]:
                continue
            event_at = datetime(year, month, day, hour, minute, tzinfo=JST)
            if event_at >= after:
                candidates.append(event_at)
        if candidates:
            break
    return candidates


def resolve_recurring_event(
    text: str,
    source_anchor: datetime,
    *,
    materialize_after: datetime,
) -> DateResolution | None:
    """Materialize the next occurrence from an explicit recurring rule.

    The source timestamp remains provenance; materialize_after only selects
    the next occurrence. No recurrence is accepted without the same event and
    announcement safety evidence used by the one-off recovery path.
    """
    if not _recovery_text_is_safe(text):
        return None

    normalized = _normalize_recovery_text(text)
    anchor_jst = _jst(source_anchor)
    after = _jst(materialize_after)

    match = DAILY_RECURRENCE_PATTERN.search(normalized)
    if match:
        parts = _clock_parts(match)
        if parts is None:
            return None
        hour, minute = parts
        event_at = datetime(after.year, after.month, after.day, hour, minute, tzinfo=JST)
        if event_at < after:
            event_at += timedelta(days=1)
        return _recurrence_resolution(
            event_at=event_at,
            source_anchor=anchor_jst,
            method="recurrence_daily_materialized",
            matched_text=match.group(0),
            recurrence_rule={
                "frequency": "daily",
                "hour": hour,
                "minute": minute,
                "timezone": "Asia/Tokyo",
            },
        )

    match = MULTI_WEEKLY_RECURRENCE_PATTERN.search(normalized)
    if match:
        parts = _clock_parts(match)
        if parts is None:
            return None
        hour, minute = parts
        weekdays = sorted({WEEKDAY_INDEX[value] for value in re.findall(r"[月火水木金土日]", match.group("weekdays"))})
        candidates: list[datetime] = []
        for weekday in weekdays:
            days_ahead = (weekday - after.weekday()) % 7
            target = after.date() + timedelta(days=days_ahead)
            event_at = datetime(target.year, target.month, target.day, hour, minute, tzinfo=JST)
            if event_at < after:
                event_at += timedelta(days=7)
            candidates.append(event_at)
        if not candidates:
            return None
        return _recurrence_resolution(
            event_at=min(candidates),
            source_anchor=anchor_jst,
            method="recurrence_multi_weekly_materialized",
            matched_text=match.group(0),
            recurrence_rule={
                "frequency": "weekly",
                "weekdays": weekdays,
                "hour": hour,
                "minute": minute,
                "timezone": "Asia/Tokyo",
            },
        )

    match = WEEKLY_RECURRENCE_PATTERN.search(normalized)
    if match:
        parts = _clock_parts(match)
        if parts is None:
            return None
        hour, minute = parts
        weekday = WEEKDAY_INDEX[match.group("weekday")]
        days_ahead = (weekday - after.weekday()) % 7
        target = after.date() + timedelta(days=days_ahead)
        event_at = datetime(target.year, target.month, target.day, hour, minute, tzinfo=JST)
        if event_at < after:
            event_at += timedelta(days=7)
        return _recurrence_resolution(
            event_at=event_at,
            source_anchor=anchor_jst,
            method="recurrence_weekly_materialized",
            matched_text=match.group(0),
            recurrence_rule={
                "frequency": "weekly",
                "weekday": weekday,
                "hour": hour,
                "minute": minute,
                "timezone": "Asia/Tokyo",
            },
        )

    match = MULTI_MONTHLY_DAY_RECURRENCE_PATTERN.search(normalized)
    if match:
        parts = _clock_parts(match)
        if parts is None:
            return None
        hour, minute = parts
        days = sorted({
            int(value)
            for value in re.findall(r"\d{1,2}", match.group("days"))
            if 1 <= int(value) <= 31
        })
        candidates = _monthly_candidates(after=after, days=days, hour=hour, minute=minute)
        if candidates:
            return _recurrence_resolution(
                event_at=min(candidates),
                source_anchor=anchor_jst,
                method="recurrence_multi_monthly_day_materialized",
                matched_text=match.group(0),
                recurrence_rule={
                    "frequency": "monthly",
                    "days": days,
                    "hour": hour,
                    "minute": minute,
                    "timezone": "Asia/Tokyo",
                },
            )

    match = MONTHLY_DAY_RECURRENCE_PATTERN.search(normalized)
    if match:
        parts = _clock_parts(match)
        if parts is None:
            return None
        hour, minute = parts
        day = int(match.group("day"))
        candidates = _monthly_candidates(after=after, days=[day], hour=hour, minute=minute)
        if candidates:
            return _recurrence_resolution(
                event_at=min(candidates),
                source_anchor=anchor_jst,
                method="recurrence_monthly_day_materialized",
                matched_text=match.group(0),
                recurrence_rule={
                    "frequency": "monthly",
                    "day": day,
                    "hour": hour,
                    "minute": minute,
                    "timezone": "Asia/Tokyo",
                },
            )

    match = LAST_WEEKDAY_MONTHLY_RECURRENCE_PATTERN.search(normalized)
    if match:
        parts = _clock_parts(match)
        if parts is None:
            return None
        hour, minute = parts
        weekday = WEEKDAY_INDEX[match.group("weekday")]
        candidates: list[datetime] = []
        for offset in range(14):
            month_index = after.month - 1 + offset
            year = after.year + month_index // 12
            month = month_index % 12 + 1
            last_day = monthrange(year, month)[1]
            last_weekday = datetime(year, month, last_day, tzinfo=JST).weekday()
            day = last_day - (last_weekday - weekday) % 7
            event_at = datetime(year, month, day, hour, minute, tzinfo=JST)
            if event_at >= after:
                candidates.append(event_at)
                break
        if candidates:
            return _recurrence_resolution(
                event_at=min(candidates),
                source_anchor=anchor_jst,
                method="recurrence_last_weekday_monthly_materialized",
                matched_text=match.group(0),
                recurrence_rule={
                    "frequency": "monthly_last_weekday",
                    "weekday": weekday,
                    "hour": hour,
                    "minute": minute,
                    "timezone": "Asia/Tokyo",
                },
            )

    match = ORDINAL_MONTHLY_RECURRENCE_PATTERN.search(normalized)
    if match:
        parts = _clock_parts(match)
        if parts is None:
            return None
        hour, minute = parts
        ordinals = sorted({
            int(value)
            for value in re.findall(r"\d+", match.group("ordinals"))
            if 1 <= int(value) <= 5
        })
        weekday = WEEKDAY_INDEX[match.group("weekday")]
        candidates: list[datetime] = []
        for offset in range(14):
            month_index = after.month - 1 + offset
            year = after.year + month_index // 12
            month = month_index % 12 + 1
            first_weekday = datetime(year, month, 1, tzinfo=JST).weekday()
            for ordinal in ordinals:
                day = 1 + (weekday - first_weekday) % 7 + 7 * (ordinal - 1)
                if day > monthrange(year, month)[1]:
                    continue
                event_at = datetime(year, month, day, hour, minute, tzinfo=JST)
                if event_at >= after:
                    candidates.append(event_at)
            if candidates:
                break
        if candidates:
            event_at = min(candidates)
            return _recurrence_resolution(
                event_at=event_at,
                source_anchor=anchor_jst,
                method="recurrence_ordinal_monthly_materialized",
                matched_text=match.group(0),
                recurrence_rule={
                    "frequency": "monthly_ordinal_weekday",
                    "ordinals": ordinals,
                    "weekday": weekday,
                    "hour": hour,
                    "minute": minute,
                    "timezone": "Asia/Tokyo",
                },
            )

    return None


def materialize_recurring_events(
    text: str,
    source_anchor: datetime,
    *,
    materialize_after: datetime,
    max_occurrences: int = 4,
    future_days: int = 120,
) -> list[DateResolution]:
    """Materialize a small rolling set of explicit future recurrence occurrences.

    The recurring expression remains the authority. The bounded four-occurrence
    projection avoids turning an old announcement into an indefinite schedule,
    while giving the public calendar more than only the next occurrence.
    """
    if max_occurrences < 1 or future_days < 1:
        return []

    after = _jst(materialize_after)
    limit = after + timedelta(days=future_days)
    cursor = after
    results: list[DateResolution] = []

    for _ in range(max_occurrences):
        resolution = resolve_recurring_event(
            text,
            source_anchor,
            materialize_after=cursor,
        )
        if resolution is None or resolution.event_at > limit:
            break
        if results and resolution.event_at <= results[-1].event_at:
            break
        results.append(resolution)
        cursor = resolution.event_at + timedelta(minutes=1)

    return results


def resolve_event_datetime(
    text: str,
    anchor: datetime,
    *,
    explicit_parser: Callable[[str, datetime], datetime | None],
) -> DateResolution | None:
    """Resolve explicit and weekday-based event dates without future leakage.

    Weekday phrases use a Monday-start calendar week. `今週` never rolls a
    past target into the following week. `来週` resolves inside the next
    calendar week, while `次の` and an unprefixed weekday use next-occurrence
    semantics.
    """
    anchor_jst = _jst(anchor)
    if RELATIVE_DAY_PATTERN.search(text) and MULTI_EVENT_CLOCK_PATTERN.search(text):
        return None

    normalized = _normalize_recovery_text(text)
    explicit = None if NONTRIVIAL_CLOCK_RE.search(normalized) else explicit_parser(text, anchor_jst)
    if explicit is not None:
        if RELATIVE_DAY_PATTERN.search(text):
            method = "relative_day_from_source_timestamp"
        elif EXPLICIT_DATE_PATTERN.search(text):
            method = "explicit_calendar_date"
        else:
            method = "explicit_datetime"
        return DateResolution(
            event_at=_jst(explicit),
            method=method,
            anchor=anchor_jst,
            matched_text="explicit",
        )

    if any(
        pattern.search(normalized)
        for pattern in (
            ORDINAL_RECURRING_WEEKDAY_PATTERN,
            MULTI_WEEKLY_RECURRENCE_PATTERN,
            WEEKLY_RECURRENCE_PATTERN,
            DAILY_RECURRENCE_PATTERN,
            MULTI_MONTHLY_DAY_RECURRENCE_PATTERN,
            MONTHLY_DAY_RECURRENCE_PATTERN,
            LAST_WEEKDAY_MONTHLY_RECURRENCE_PATTERN,
            ORDINAL_MONTHLY_RECURRENCE_PATTERN,
        )
    ):
        return None

    match = WEEKDAY_PATTERN.search(normalized)
    if not match:
        return _resolve_evidence_span_datetime(text, anchor_jst)

    target_weekday = WEEKDAY_INDEX[match.group("weekday")]
    prefix = (match.group("prefix") or "").strip()
    if not prefix and UNPREFIXED_WEEKDAY_PAST_CONTEXT_RE.search(text):
        return None
    parts = _clock_parts(match)
    if parts is None:
        return None
    hour, minute = parts
    week_start = anchor_jst.date() - timedelta(days=anchor_jst.weekday())

    if prefix.startswith("来週"):
        target_date = week_start + timedelta(days=7 + target_weekday)
        method = "next_calendar_week_weekday"
    elif prefix.startswith("今週"):
        target_date = week_start + timedelta(days=target_weekday)
        method = "current_calendar_week_weekday"
    else:
        days_ahead = (target_weekday - anchor_jst.weekday()) % 7
        if prefix.startswith("次") and days_ahead == 0:
            days_ahead = 7
        target_date = anchor_jst.date() + timedelta(days=days_ahead)
        method = (
            "next_occurrence_explicit"
            if prefix.startswith("次")
            else "next_occurrence_unprefixed"
        )

    resolved = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        hour,
        minute,
        tzinfo=JST,
    )

    if prefix.startswith("今週") and resolved < anchor_jst:
        return None
    if not prefix and resolved < anchor_jst - timedelta(hours=2):
        resolved += timedelta(days=7)

    return DateResolution(
        event_at=resolved,
        method=method,
        anchor=anchor_jst,
        matched_text=match.group(0)[:160],
    )


def install_classifier_datetime(
    corpus: Any,
    implementation: Any,
) -> None:
    """Install the corrected parser after the existing v1.8 classifier setup."""
    explicit_parser = corpus._ORIGINAL_PARSE_EVENT_DATETIME
    base_candidate_to_event = corpus.refined_candidate_to_event

    def parse_datetime(text: str, anchor: datetime) -> datetime | None:
        resolution = resolve_event_datetime(
            text,
            anchor,
            explicit_parser=explicit_parser,
        )
        return resolution.event_at if resolution else None

    def candidate_to_event(
        candidate: dict[str, Any],
        *,
        now: datetime,
        min_retweets: int,
        x_ids: set[str],
    ) -> tuple[dict[str, Any] | None, str | None]:
        event, reason = base_candidate_to_event(
            candidate,
            now=now,
            min_retweets=min_retweets,
            x_ids=x_ids,
        )
        if not event:
            return event, reason
        resolution = resolve_event_datetime(
            str(candidate.get("text") or ""),
            now,
            explicit_parser=explicit_parser,
        )
        if resolution is None:
            return None, "missing_datetime"
        evidence = resolution.evidence(implementation.utc_text)
        event["date_resolution_method"] = evidence["method"]
        event["date_resolution_anchor"] = evidence["anchor"]
        event["date_resolution_evidence"] = evidence
        return event, reason

    implementation.parse_event_datetime = parse_datetime
    corpus.parse_event_datetime_v18 = parse_datetime
    corpus.refined_candidate_to_event = candidate_to_event


def build_resolution_audit(
    previous_events: list[dict[str, Any]],
    current_events: list[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    previous_by_id = {
        str(event.get("source_id")): event
        for event in previous_events
        if event.get("source_id")
    }
    current_by_id = {
        str(event.get("source_id")): event
        for event in current_events
        if event.get("source_id")
    }
    changes: list[dict[str, Any]] = []
    for source_id in sorted(previous_by_id.keys() & current_by_id.keys()):
        previous_start = previous_by_id[source_id].get("starts_at")
        current = current_by_id[source_id]
        current_start = current.get("starts_at")
        if previous_start == current_start:
            continue
        changes.append(
            {
                "source_id": source_id,
                "previous_starts_at": previous_start,
                "current_starts_at": current_start,
                "date_resolution_method": current.get("date_resolution_method"),
                "date_resolution_anchor": current.get("date_resolution_anchor"),
            }
        )

    methods = Counter(
        str(event.get("date_resolution_method") or "missing")
        for event in current_events
    )
    return {
        "schema_version": "1.0",
        "policy_version": "calendar-week-relative-date.v1",
        "generated_at": generated_at,
        "timezone": "Asia/Tokyo",
        "week_start": "monday",
        "previous_event_count": len(previous_events),
        "current_event_count": len(current_events),
        "events_with_resolution_evidence": sum(
            bool(event.get("date_resolution_evidence")) for event in current_events
        ),
        "resolution_method_counts": dict(sorted(methods.items())),
        "changed_event_count": len(changes),
        "changed_events": changes,
    }
