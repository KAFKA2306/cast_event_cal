from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def load_module():
    path = Path(__file__).parents[1] / "scripts" / "fetch_external_calendars.py"
    spec = importlib.util.spec_from_file_location("fetch_external_calendars", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_google_public_ics_url_encodes_calendar_id():
    module = load_module()
    assert module.google_public_ics_url("abc@group.calendar.google.com") == (
        "https://calendar.google.com/calendar/ical/abc%40group.calendar.google.com/public/basic.ics"
    )


def test_parse_ics_expands_rrule_inside_window():
    module = load_module()
    source = """BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:weekly-1\r\nDTSTART;TZID=Asia/Tokyo:20260804T220000\r\nDTEND;TZID=Asia/Tokyo:20260804T230000\r\nRRULE:FREQ=WEEKLY;COUNT=3\r\nSUMMARY:VRChat.rb\r\nORGANIZER;CN=いとじゅん:mailto:test@example.com\r\nLOCATION:VRChat\r\nURL:https://example.com/events/ruby\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""
    events = module.parse_ics_events(
        source,
        source_name="hub",
        fetched_at="2026-08-03T00:00:00Z",
        source_page="https://example.com/",
        tags=["技術"],
        default_timezone="Asia/Tokyo",
        window_start=datetime(2026, 8, 3, tzinfo=UTC),
        window_end=datetime(2026, 8, 31, tzinfo=UTC),
        max_events=20,
    )
    assert len(events) == 3
    assert events[0]["starts_at"] == "2026-08-04T13:00:00Z"
    assert events[0]["ends_at"] == "2026-08-04T14:00:00Z"
    assert events[0]["organizer"] == "いとじゅん"
    assert events[0]["tags"] == ["技術"]


def test_extract_jsonld_event_from_official_page():
    module = load_module()
    html = """
    <html><head><script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "EducationEvent",
      "@id": "/events/42",
      "name": "ML集会",
      "startDate": "2026-08-05T21:30:00+09:00",
      "endDate": "2026-08-05T22:30:00+09:00",
      "eventStatus": "https://schema.org/EventScheduled",
      "location": {"@type": "VirtualLocation", "name": "VRChat"},
      "organizer": {"@type": "Organization", "name": "ML集会運営"},
      "image": {"url": "/images/ml.webp"},
      "url": "/events/42"
    }
    </script></head></html>
    """
    events = module.extract_jsonld_events(
        html,
        page_url="https://official.example/events/",
        source_name="official",
        fetched_at="2026-08-03T00:00:00Z",
        tags=["公式サイト"],
        default_timezone="Asia/Tokyo",
    )
    assert len(events) == 1
    event = events[0]
    assert event["starts_at"] == "2026-08-05T12:30:00Z"
    assert event["organizer"] == "ML集会運営"
    assert event["location"] == "VRChat"
    assert event["url"] == "https://official.example/events/42"
    assert event["image_url"] == "https://official.example/images/ml.webp"


def test_permissioned_vrceve_source_is_skipped_without_approval(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.delenv("VRCEVE_DATA_USE_APPROVED", raising=False)
    monkeypatch.delenv("VRCEVE_ICS_URL", raising=False)
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()
    config = {
        "sources": [
            {
                "name": "vrceve_authorized_feed",
                "type": "permissioned_ics",
                "enabled": True,
                "approval_env": "VRCEVE_DATA_USE_APPROVED",
                "url_env": "VRCEVE_ICS_URL",
                "source_page": "https://vrceve.com/",
                "policy_url": "https://vrceve.com/policy/",
            }
        ]
    }
    config_path = config_dir / "external_calendars.yaml"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    output = data_dir / "external_events.json"
    health = data_dir / "external_health.json"
    assert module.run_collection(config_path=config_path, output=output, health_output=health) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == []
    health_payload = json.loads(health.read_text(encoding="utf-8"))
    assert health_payload["status"] == "skipped"
    assert health_payload["sources"][0]["status"] == "skipped"
    assert "not approved" in health_payload["sources"][0]["error"]


def test_cross_source_dedup_uses_url_or_exact_title_and_minute():
    module = load_module()
    existing = [{"title": "Web技術集会", "starts_at": "2026-08-05T13:00:00Z", "url": "https://example.com/e/1"}]
    incoming = [
        {"title": "Ｗｅｂ 技術集会", "starts_at": "2026-08-05T13:00:30Z", "url": "https://other.example/event"},
        {"title": "別イベント", "starts_at": "2026-08-05T14:00:00Z", "url": "https://example.com/e/2"},
    ]
    selected, excluded = module.deduplicate_external(incoming, existing)
    assert excluded == 1
    assert [row["title"] for row in selected] == ["別イベント"]
