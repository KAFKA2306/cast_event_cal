from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.relative_datetime import resolve_recurring_event


JST = ZoneInfo("Asia/Tokyo")
ANCHOR = datetime(2026, 9, 29, 12, 0, tzinfo=JST)
AFTER = datetime(2026, 9, 30, 0, 0, tzinfo=JST)


def test_daily_recurrence_does_not_borrow_clock_from_next_weekly_clause():
    text = "毎日カフェ営業しています。それに毎週土曜22時は交流会を開催します。"

    resolution = resolve_recurring_event(text, ANCHOR, materialize_after=AFTER)

    assert resolution is not None
    assert resolution.method == "recurrence_weekly_materialized"
    assert resolution.recurrence_rule is not None
    assert resolution.recurrence_rule["frequency"] == "weekly"
    assert resolution.event_at.weekday() == 5
    assert (resolution.event_at.hour, resolution.event_at.minute) == (22, 0)


def test_same_clause_daily_recurrence_keeps_its_clock():
    text = "毎日22時にカフェ営業します。"

    resolution = resolve_recurring_event(text, ANCHOR, materialize_after=AFTER)

    assert resolution is not None
    assert resolution.method == "recurrence_daily_materialized"
    assert resolution.recurrence_rule is not None
    assert resolution.recurrence_rule["frequency"] == "daily"
    assert (resolution.event_at.hour, resolution.event_at.minute) == (22, 0)
