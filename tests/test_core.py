from datetime import UTC, datetime

from cast_event_cal.core import Event, deduplicate, parse_ics, render_ics, x_post_to_event


def test_parse_ics_timezone_and_render_roundtrip():
    source = """BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:test-1\r\nDTSTART;TZID=Asia/Tokyo:20260802T210000\r\nDTEND;TZID=Asia/Tokyo:20260802T220000\r\nSUMMARY:テスト集会\r\nLOCATION:Example World\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""
    events = parse_ics(source, "sample", "2026-08-02T00:00:00Z")
    assert len(events) == 1
    assert events[0].starts_at == "2026-08-02T12:00:00Z"
    rendered = render_ics(events, datetime(2026, 8, 2, tzinfo=UTC))
    assert "SUMMARY:テスト集会" in rendered
    assert "DTSTART:20260802T120000Z" in rendered


def test_deduplicate_uses_source_identity():
    first = Event(id="same", title="A", starts_at="2026-08-02T12:00:00Z", source="one", fetched_at="2026-08-01T00:00:00Z")
    latest = Event(id="same", title="B", starts_at="2026-08-02T12:00:00Z", source="one", fetched_at="2026-08-02T00:00:00Z")
    assert deduplicate([first, latest])[0].title == "B"


def test_x_parser_rejects_ambiguous_post_and_accepts_explicit_datetime():
    assert x_post_to_event({"id": "1", "text": "今夜イベントです", "created_at": "2026-08-02T00:00:00Z"}, {}, "x", "2026-08-02T00:00:00Z") is None
    event = x_post_to_event(
        {"id": "2", "author_id": "u", "text": "8/3 21:30 VRChat集会を開催", "created_at": "2026-08-02T00:00:00Z"},
        {"u": "host"},
        "x",
        "2026-08-02T00:00:00Z",
    )
    assert event is not None
    assert event.starts_at == "2026-08-03T12:30:00Z"
    assert event.organizer == "@host"
