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
    assert events[0]["source_page"] == "https://example.com/"
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


def test_shared_source_page_does_not_collapse_distinct_events_at_same_minute():
    module = load_module()
    source_page = "https://vrc-ta-hub.com/event/list/"
    incoming = [
        {
            "title": "VR研究Cafe",
            "starts_at": "2026-09-20T12:00:00Z",
            "url": source_page,
            "source_page": source_page,
        },
        {
            "title": "分散システム集会",
            "starts_at": "2026-09-20T12:00:00Z",
            "url": source_page,
            "source_page": source_page,
        },
    ]
    selected, excluded = module.deduplicate_external(incoming, [])
    assert excluded == 0
    assert [row["title"] for row in selected] == ["VR研究Cafe", "分散システム集会"]


def test_event_specific_url_only_deduplicates_same_occurrence_minute():
    module = load_module()
    existing = [
        {
            "title": "Original title",
            "starts_at": "2026-09-20T12:00:00Z",
            "url": "https://vrchat.com/home/group/grp_example",
        }
    ]
    incoming = [
        {
            "title": "Renamed event",
            "starts_at": "2026-09-20T12:00:30Z",
            "url": "https://vrchat.com/home/group/grp_example",
        },
        {
            "title": "Next occurrence",
            "starts_at": "2026-09-27T12:00:00Z",
            "url": "https://vrchat.com/home/group/grp_example",
        },
    ]
    selected, excluded = module.deduplicate_external(incoming, existing)
    assert excluded == 1
    assert [row["title"] for row in selected] == ["Next occurrence"]

def test_parse_vrc_search_curated_events_uses_calendar_id_and_utc():
    module = load_module()
    html = """
    <html><body>
      <article class="list-group-item result-row result-row-event">
        <a class="result-row-title">喫茶「はたご」通常営業日</a>
        <div>開始 2026-09-25 10:00 終了 2026-09-25 12:00</div>
        <p class="result-row-desc">19時から <b>Group+</b> でオープンします。</p>
        <a href="/ja/groups/grp_12345678-abcd">喫茶「はたご」</a>
        <a href="https://vrchat.com/home/group/grp_12345678-abcd/calendar/cal_abcdef12-3456-7890-abcd-ef1234567890">VRChatで見る</a>
      </article>
    </body></html>
    """
    events = module.parse_vrc_search_events(
        html,
        page_url="https://search.vrcwwt.com/ja/events/hangout/next-month/",
        source_name="vrc_search_public_japanese",
        fetched_at="2026-09-25T20:00:00Z",
        tags=["日本語公開イベント"],
        window_start=datetime(2026, 9, 25, tzinfo=UTC),
        window_end=datetime(2026, 10, 25, tzinfo=UTC),
    )
    assert len(events) == 1
    event = events[0]
    assert event["source_id"] == "cal_abcdef12-3456-7890-abcd-ef1234567890"
    assert event["starts_at"] == "2026-09-25T10:00:00Z"
    assert event["ends_at"] == "2026-09-25T12:00:00Z"
    assert event["organizer"] == "喫茶「はたご」"
    assert event["location"] == "VRChat"
    assert event["category"] == "hangout"
    assert event["url"].startswith("https://vrchat.com/home/group/")
    assert "Group+" in event["description"]
    assert "VRC Search" in event["tags"]


def test_vrc_search_parser_deduplicates_same_calendar_event_across_pages():
    module = load_module()
    card = """
      <article class="list-group-item result-row result-row-event">
        <a class="result-row-title">同じイベント</a>
        <div>開始 2026-09-26 12:00 終了 2026-09-26 13:00</div>
        <p class="result-row-desc">公開イベントです。</p>
        <a href="/groups/grp_example">主催グループ</a>
        <a href="https://vrchat.com/home/group/grp_example/calendar/cal_aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee">VRChatで見る</a>
      </article>
    """
    kwargs = {
        "source_name": "vrc_search_public_japanese",
        "fetched_at": "2026-09-25T20:00:00Z",
        "tags": [],
        "window_start": datetime(2026, 9, 25, tzinfo=UTC),
        "window_end": datetime(2026, 10, 25, tzinfo=UTC),
    }
    music = module.parse_vrc_search_events(
        card,
        page_url="https://search.vrcwwt.com/ja/events/music/next-month/",
        **kwargs,
    )
    dance = module.parse_vrc_search_events(
        card,
        page_url="https://search.vrcwwt.com/ja/events/dance/next-month/",
        **kwargs,
    )
    selected, excluded = module.deduplicate_external([*music, *dance], [])
    assert len(selected) == 1
    assert excluded == 1

def test_parse_vrc_search_english_curated_time_format():
    module = load_module()
    html = """
    <html><body>
      <article class="list-group-item result-row result-row-event">
        <a class="result-row-title">Mobility Monday</a>
        <div>Starts Tue, Sep 29, 2026 12:00 AM Ends Tue, Sep 29, 2026 01:00 AM</div>
        <p class="result-row-desc">Exercise session for all ability levels.</p>
        <a href="/groups/grp_12345678-abcd">VR Wellness Center</a>
        <a href="https://vrchat.com/home/group/grp_12345678-abcd/calendar/cal_12345678-aaaa-bbbb-cccc-dddddddddddd">View on VRChat</a>
      </article>
    </body></html>
    """
    events = module.parse_vrc_search_events(
        html,
        page_url="https://search.vrcwwt.com/events/english/next-week/",
        source_name="vrc_search_public_events",
        fetched_at="2026-09-26T00:00:00Z",
        tags=["公開VRChatイベント"],
        window_start=datetime(2026, 9, 26, tzinfo=UTC),
        window_end=datetime(2026, 10, 26, tzinfo=UTC),
    )
    assert len(events) == 1
    assert events[0]["starts_at"] == "2026-09-29T00:00:00Z"
    assert events[0]["ends_at"] == "2026-09-29T01:00:00Z"
    assert events[0]["source_id"] == "cal_12345678-aaaa-bbbb-cccc-dddddddddddd"
    assert events[0]["organizer"] == "VR Wellness Center"



def test_parse_vrc_search_localized_numeric_datetime_labels():
    module = load_module()
    cases = [
        ("Empieza 2026-09-26 01:00 Termina 2026-09-26 02:00", "2026-09-26T01:00:00Z", "2026-09-26T02:00:00Z"),
        ("Beginnt 2026-09-27 03:00 Endet 2026-09-27 04:00", "2026-09-27T03:00:00Z", "2026-09-27T04:00:00Z"),
        ("Начало 2026-09-28 05:00 Окончание 2026-09-28 06:00", "2026-09-28T05:00:00Z", "2026-09-28T06:00:00Z"),
        ("Commence 2026-09-29 07:00 Se termine 2026-09-29 08:00", "2026-09-29T07:00:00Z", "2026-09-29T08:00:00Z"),
        ("시작 2026-09-30 09:00 종료 2026-09-30 10:00", "2026-09-30T09:00:00Z", "2026-09-30T10:00:00Z"),
    ]
    for text, expected_start, expected_end in cases:
        start = module.parse_vrc_search_datetime(text)
        end = module.parse_vrc_search_datetime(text, end=True)
        assert start is not None and module.utc_text(start) == expected_start
        assert end is not None and module.utc_text(end) == expected_end
