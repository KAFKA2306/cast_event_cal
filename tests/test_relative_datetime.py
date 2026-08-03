from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.relative_datetime import build_resolution_audit, resolve_event_datetime

JST = ZoneInfo("Asia/Tokyo")


def no_explicit_date(_text: str, _anchor: datetime) -> None:
    return None


def resolve(text: str, anchor: datetime):
    return resolve_event_datetime(
        text,
        anchor,
        explicit_parser=no_explicit_date,
    )


def test_friday_next_week_monday_is_three_days_later() -> None:
    anchor = datetime(2026, 8, 7, 12, 0, tzinfo=JST)
    result = resolve("来週月曜 22:00 VRChatイベント", anchor)
    assert result is not None
    assert result.event_at == datetime(2026, 8, 10, 22, 0, tzinfo=JST)
    assert result.method == "next_calendar_week_weekday"


def test_sunday_next_week_saturday_is_six_days_later() -> None:
    anchor = datetime(2026, 8, 9, 12, 0, tzinfo=JST)
    result = resolve("来週土曜日 21:00 開催", anchor)
    assert result is not None
    assert result.event_at == datetime(2026, 8, 15, 21, 0, tzinfo=JST)


def test_monday_next_week_friday_is_eleven_days_later() -> None:
    anchor = datetime(2026, 8, 3, 9, 0, tzinfo=JST)
    result = resolve("来週の金曜日 20:30 OPEN", anchor)
    assert result is not None
    assert result.event_at == datetime(2026, 8, 14, 20, 30, tzinfo=JST)


def test_past_current_week_weekday_is_rejected_not_rolled_forward() -> None:
    anchor = datetime(2026, 8, 4, 12, 0, tzinfo=JST)
    assert resolve("今週月曜 22:00 のイベント", anchor) is None


def test_unprefixed_weekday_uses_next_occurrence() -> None:
    anchor = datetime(2026, 8, 3, 9, 0, tzinfo=JST)
    result = resolve("水曜 21:00 JOIN", anchor)
    assert result is not None
    assert result.event_at == datetime(2026, 8, 5, 21, 0, tzinfo=JST)
    assert result.method == "next_occurrence_unprefixed"


def test_next_same_weekday_means_seven_days_later() -> None:
    anchor = datetime(2026, 8, 3, 9, 0, tzinfo=JST)
    result = resolve("次の月曜 19:00 開催", anchor)
    assert result is not None
    assert result.event_at == datetime(2026, 8, 10, 19, 0, tzinfo=JST)
    assert result.method == "next_occurrence_explicit"


def test_jst_week_boundary_is_used_even_when_anchor_is_utc() -> None:
    anchor_utc = datetime.fromisoformat("2026-08-09T14:59:00+00:00")
    result = resolve("来週月曜 00:30 開催", anchor_utc)
    assert result is not None
    assert result.anchor == datetime(2026, 8, 9, 23, 59, tzinfo=JST)
    assert result.event_at == datetime(2026, 8, 10, 0, 30, tzinfo=JST)


def test_same_day_unprefixed_future_stays_today_and_old_time_moves_next_week() -> None:
    anchor = datetime(2026, 8, 3, 18, 0, tzinfo=JST)
    future = resolve("月曜 21:00 開催", anchor)
    old = resolve("月曜 12:00 開催", anchor)
    assert future is not None and future.event_at.date() == anchor.date()
    assert old is not None and old.event_at.date().isoformat() == "2026-08-10"


def test_resolution_audit_records_changed_existing_events() -> None:
    previous = [
        {
            "source_id": "yahoo:x:1",
            "starts_at": "2026-08-17T13:00:00Z",
        }
    ]
    current = [
        {
            "source_id": "yahoo:x:1",
            "starts_at": "2026-08-10T13:00:00Z",
            "date_resolution_method": "next_calendar_week_weekday",
            "date_resolution_anchor": "2026-08-07T03:00:00Z",
            "date_resolution_evidence": {"method": "next_calendar_week_weekday"},
        }
    ]
    audit = build_resolution_audit(
        previous,
        current,
        generated_at="2026-08-03T00:00:00Z",
    )
    assert audit["changed_event_count"] == 1
    assert audit["events_with_resolution_evidence"] == 1
    assert audit["changed_events"][0]["previous_starts_at"] == "2026-08-17T13:00:00Z"
    assert audit["changed_events"][0]["current_starts_at"] == "2026-08-10T13:00:00Z"
