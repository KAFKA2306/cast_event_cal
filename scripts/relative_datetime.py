from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
FULLWIDTH_DIGIT_TRANSLATION = str.maketrans("０１２３４５６７８９", "0123456789")
EVIDENCE_SPAN_CHARS = 160
WEEKDAY_INDEX = {name: index for index, name in enumerate("月火水木金土日")}
WEEKDAY_PATTERN = re.compile(
    r"(?P<prefix>次(?:の)?|来週(?:の)?|今週(?:の)?)?\s*"
    r"(?P<weekday>[月火水木金土日])曜日?.{0,100}?"
    r"(?P<hour>[01]?\d|2[0-3])(?:[:時](?P<minute>\d{2})?)",
    flags=re.IGNORECASE | re.DOTALL,
)
ORDINAL_RECURRING_WEEKDAY_PATTERN = re.compile(
    r"(?:毎月\s*)?第\s*\d+(?:\s*[、,・/]\s*第?\s*\d+)*\s*[月火水木金土日]曜(?:日)?",
    flags=re.IGNORECASE,
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
CLOCK_PATTERN = re.compile(
    r"(?<!\d)(?P<hour>[01]?\d|2[0-3])(?:[:：時]\s*(?P<minute>\d{0,2}))(?!\d)"
)
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

    def evidence(self, utc_text: Callable[[datetime], str]) -> dict[str, str]:
        return {
            "method": self.method,
            "anchor": utc_text(self.anchor),
            "resolved_at": utc_text(self.event_at),
            "timezone": "Asia/Tokyo",
            "week_start": "monday",
            "matched_text": self.matched_text,
        }


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


def _match_gap(left: re.Match[str], right: re.Match[str]) -> int:
    if left.end() <= right.start():
        return right.start() - left.end()
    if right.end() <= left.start():
        return left.start() - right.end()
    return 0


def _recovery_text_is_safe(text: str) -> bool:
    if not RECOVERY_EVENT_RE.search(text) or not RECOVERY_ANNOUNCEMENT_RE.search(text):
        return False
    access = bool(RECOVERY_ACCESS_RE.search(text))
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
    try:
        value = datetime(
            year,
            month,
            day,
            int(clock.group("hour")),
            int(clock.group("minute") or 0),
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

    explicit = explicit_parser(text, anchor_jst)
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

    normalized = (
        text.replace("：", ":")
        .replace("／", "/")
        .replace("．", ".")
        .replace("－", "-")
        .replace("〜", "~")
        .replace("～", "~")
    )
    if ORDINAL_RECURRING_WEEKDAY_PATTERN.search(normalized):
        return None

    match = WEEKDAY_PATTERN.search(normalized)
    if not match:
        return _resolve_evidence_span_datetime(text, anchor_jst)

    target_weekday = WEEKDAY_INDEX[match.group("weekday")]
    prefix = (match.group("prefix") or "").strip()
    if not prefix and UNPREFIXED_WEEKDAY_PAST_CONTEXT_RE.search(text):
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
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
