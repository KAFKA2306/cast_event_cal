from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from scripts.render_search_pages import render as render_events
from scripts.render_social_assets import render as render_social


def _root(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(
        '<!doctype html><html><head><style>:root{--line:#ddd;--radius:20px;--muted:#666}.eyebrow{}</style></head>'
        '<body><a class="button" href="calendar.ics">カレンダーを購読</a><footer>footer</footer></body></html>',
        encoding="utf-8",
    )
    return tmp_path


def test_social_cards_cover_every_indexable_event_and_patch_share_ui(tmp_path: Path) -> None:
    root = _root(tmp_path)
    payload = {
        "generated_at": "2026-08-16T00:00:00Z",
        "events": [
            {
                "id": "music-1",
                "title": "Music Meetup One",
                "canonical_name": "Music Meetup One",
                "starts_at": "2026-08-17T12:00:00Z",
                "ends_at": "2026-08-17T13:30:00Z",
                "category": "music",
                "category_label": "Music and Dance",
                "description": "Meet, dance, and talk.",
                "primary_action_url": "https://official.example/music-1",
            },
            {
                "id": "community-1",
                "title": "Community Meetup Two",
                "canonical_name": "Community Meetup Two",
                "starts_at": "2026-08-18T12:00:00Z",
                "category": "community",
                "category_label": "Community",
                "primary_action_url": "https://official.example/community-1",
            },
            {
                "id": "review-1",
                "title": "Review Required",
                "starts_at": "2026-08-19T12:00:00Z",
                "category": "music",
                "review_required": True,
                "primary_action_url": "https://official.example/review",
            },
        ],
    }
    events_path = root / "events.json"
    events_path.write_text(json.dumps(payload), encoding="utf-8")
    base = "https://example.test/project"
    render_events(events_path, root, base)

    result = render_social(events_path, root, base)

    assert result == {
        "indexable_count": 2,
        "og_image_count": 2,
        "share_enabled_count": 2,
        "calendar_enabled_count": 2,
    }
    images = sorted((root / "og/events").glob("*.png"))
    assert [path.name for path in images] == ["community-1.png", "music-1.png"]
    digests = []
    for path in images:
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.size == (1200, 630)
            assert image.mode == "RGB"
        digests.append(hashlib.sha256(path.read_bytes()).hexdigest())
    assert len(set(digests)) == 2

    page = (root / "events/music-1/index.html").read_text(encoding="utf-8")
    assert 'property="og:image" content="https://example.test/project/og/events/music-1.png"' in page
    assert 'property="og:image:width" content="1200"' in page
    assert 'property="og:image:height" content="630"' in page
    assert 'name="twitter:card" content="summary_large_image"' in page
    assert 'name="twitter:image" content="https://example.test/project/og/events/music-1.png"' in page
    assert 'src="../../share.js"' in page
    assert 'data-track="share_click"' in page
    assert 'data-destination-type="native"' in page
    assert 'data-destination-type="x"' in page
    assert 'href="event.ics"' in page
    assert 'data-track="calendar_event_download"' in page
    assert 'data-destination-type="ics"' in page
    assert "utm_source=share" in page
    assert "utm_source%3Dx" in page
    share_block = page.split("share-controls:start", 1)[1].split("share-controls:end", 1)[0]
    assert "https://official.example/music-1" not in share_block
    share_js = (root / "share.js").read_text(encoding="utf-8")
    assert "navigator.share" in share_js
    assert "navigator.clipboard" in share_js

    calendar = (root / "events/music-1/event.ics").read_bytes()
    assert b"\r\n" in calendar
    calendar_text = calendar.decode("utf-8")
    assert "BEGIN:VCALENDAR\r\n" in calendar_text
    assert "BEGIN:VEVENT\r\n" in calendar_text
    assert "UID:music-1@kafka2306.github.io\r\n" in calendar_text
    assert "DTSTAMP:20260816T000000Z\r\n" in calendar_text
    assert "DTSTART:20260817T120000Z\r\n" in calendar_text
    assert "DTEND:20260817T133000Z\r\n" in calendar_text
    assert "SUMMARY:Music Meetup One\r\n" in calendar_text
    assert "URL:https://example.test/project/events/music-1/\r\n" in calendar_text
    assert calendar_text.endswith("END:VCALENDAR\r\n")

    no_end_calendar = (root / "events/community-1/event.ics").read_text(encoding="utf-8")
    assert "DTSTART:20260818T120000Z" in no_end_calendar
    assert "DTEND:" not in no_end_calendar
    assert not (root / "events/review-1/event.ics").exists()


def test_social_render_is_idempotent(tmp_path: Path) -> None:
    root = _root(tmp_path)
    payload = {
        "generated_at": "2026-08-16T00:00:00Z",
        "events": [
            {
                "id": "event-1",
                "title": "Stable Social Card",
                "starts_at": "2026-08-17T12:00:00Z",
                "category": "community",
                "category_label": "Community",
                "primary_action_url": "https://official.example/event-1",
            }
        ],
    }
    events_path = root / "events.json"
    events_path.write_text(json.dumps(payload), encoding="utf-8")
    base = "https://example.test/project"
    render_events(events_path, root, base)

    render_social(events_path, root, base)
    page_first = (root / "events/event-1/index.html").read_bytes()
    image_first = (root / "og/events/event-1.png").read_bytes()
    calendar_first = (root / "events/event-1/event.ics").read_bytes()

    render_social(events_path, root, base)

    assert (root / "events/event-1/index.html").read_bytes() == page_first
    assert (root / "og/events/event-1.png").read_bytes() == image_first
    assert (root / "events/event-1/event.ics").read_bytes() == calendar_first
    text = (root / "events/event-1/index.html").read_text(encoding="utf-8")
    assert text.count("social-meta:start") == 1
    assert text.count("share-controls:start") == 1
