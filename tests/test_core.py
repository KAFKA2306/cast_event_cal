import json
from datetime import UTC, datetime

from cast_event_cal.core import Event, build_event, deduplicate, parse_ics, render_ics, write_outputs, x_post_to_event


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



def test_datetime_provenance_survives_normalization_and_public_output(tmp_path):
    raw = {
        "source_id": "yahoo:x:1",
        "title": "今夜のVRChatイベント",
        "starts_at": "2026-09-25T13:00:00Z",
        "category": "event",
        "date_resolution_method": "relative_day_evidence_span",
        "date_resolution_anchor": "2026-09-25T03:00:00Z",
        "date_resolution_evidence": {
            "method": "relative_day_evidence_span",
            "matched_text": "今夜 22:00",
            "timezone": "Asia/Tokyo",
        },
        "temporal_status": "upcoming",
        "is_archived": False,
    }
    event = build_event(raw, "yahoo_realtime_events", "2026-09-25T03:01:00Z")
    assert event.date_resolution_method == "relative_day_evidence_span"
    assert event.date_resolution_evidence == raw["date_resolution_evidence"]
    assert event.temporal_status == "upcoming"

    write_outputs(
        [event],
        {"status": "ok", "generated_at": "2026-09-25T03:01:00Z"},
        tmp_path,
        datetime(2026, 9, 25, 3, 1, tzinfo=UTC),
    )
    payload = json.loads((tmp_path / "events.json").read_text(encoding="utf-8"))
    published = payload["events"][0]
    assert published["date_resolution_method"] == "relative_day_evidence_span"
    assert published["date_resolution_evidence"]["matched_text"] == "今夜 22:00"
    assert published["temporal_status"] == "upcoming"
    assert published["is_archived"] is False

def test_core_outputs_leave_html_to_canonical_frontend_renderer(tmp_path):
    generated_at = datetime(2026, 8, 16, tzinfo=UTC)
    write_outputs([], {"status": "ok", "generated_at": "2026-08-16T00:00:00Z"}, tmp_path, generated_at)

    assert {path.name for path in tmp_path.iterdir()} == {"events.json", "calendar.ics", "health.json", ".nojekyll"}
    assert not (tmp_path / "index.html").exists()
