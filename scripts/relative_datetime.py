from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
WEEKDAY_INDEX = {name: index for index, name in enumerate("月火水木金土日")}
WEEKDAY_PATTERN = re.compile(
    r"(?P<prefix>次(?:の)?|来週(?:の)?|今週(?:の)?)?\s*"
    r"(?P<weekday>[月火水木金土日])曜日?.{0,100}?"
    r"(?P<hour>[01]?\d|2[0-3])(?:[:時](?P<minute>\d{2})?)",
    flags=re.IGNORECASE | re.DOTALL,
)
RELATIVE_DAY_PATTERN = re.compile(r"本日|今日|明日")
EXPLICIT_DATE_PATTERN = re.compile(
    r"(?:20\d{2}[./年-])?\d{1,2}[./月-]\d{1,2}日?"
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
    match = WEEKDAY_PATTERN.search(normalized)
    if not match:
        return None

    target_weekday = WEEKDAY_INDEX[match.group("weekday")]
    prefix = (match.group("prefix") or "").strip()
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
