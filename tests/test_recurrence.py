from datetime import datetime
from zoneinfo import ZoneInfo

from cast_event_cal.recurrence import resolve_recurrence

JST = ZoneInfo("Asia/Tokyo")


def test_weekly_materializes_next_explicit_weekday_and_clock():
    result = resolve_recurrence(
        "毎週金曜日 22:00から集会を開催します",
        after=datetime(2026, 10, 1, 8, 0, tzinfo=JST),
    )
    assert result["status"] == "resolved"
    assert result["rule"]["frequency"] == "weekly"
    assert result["occurrences"] == ["2026-10-02T22:00:00+09:00"]


def test_ordinal_weekday_materializes_monthly_without_guessing_date():
    result = resolve_recurrence(
        "第2・第4金曜日 21時30分 VRChat交流会",
        after=datetime(2026, 10, 1, 8, 0, tzinfo=JST),
        count=2,
    )
    assert result["status"] == "resolved"
    assert result["rule"]["frequency"] == "monthly_ordinal"
    assert result["occurrences"] == [
        "2026-10-09T21:30:00+09:00",
        "2026-10-23T21:30:00+09:00",
    ]


def test_recurrence_without_clock_fails_closed():
    result = resolve_recurrence(
        "毎週土曜日に集会を開催します",
        after=datetime(2026, 10, 1, 8, 0, tzinfo=JST),
    )
    assert result == {
        "status": "unresolved",
        "reason": "incomplete_or_unsupported_recurrence",
        "resolver_version": "recurrence-v1",
    }


def test_weekday_without_explicit_recurrence_fails_closed():
    result = resolve_recurrence(
        "金曜日 22:00から集会を開催します",
        after=datetime(2026, 10, 1, 8, 0, tzinfo=JST),
    )
    assert result["status"] == "unresolved"
