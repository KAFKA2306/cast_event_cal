from __future__ import annotations

import json
from pathlib import Path

from scripts.render_search_pages import render


def _root(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(
        '<!doctype html><html><head><style>:root{--line:#ddd;--radius:20px;--muted:#666}.eyebrow{}</style></head>'
        '<body><a class="button" href="calendar.ics">カレンダーを購読</a><footer>footer</footer></body></html>',
        encoding="utf-8",
    )
    return tmp_path


def test_render_search_pages_is_truthful_bounded_and_idempotent(tmp_path: Path) -> None:
    root = _root(tmp_path)
    payload = {
        "generated_at": "2026-08-16T00:00:00Z",
        "events": [
            {
                "id": "future-1",
                "title": "未来のVRChatイベント <test>",
                "starts_at": "2026-08-17T12:00:00Z",
                "ends_at": None,
                "category": "music",
                "category_label": "音楽・ダンス",
                "organizer": "@example",
                "description": "公式告知から観測した説明 & 詳細",
                "source": "official",
                "fetched_at": "2026-08-16T00:00:00Z",
                "primary_action_url": "https://example.com/event",
                "primary_action_kind": "announcement",
                "provenance": [{"url": "https://example.com/event"}],
            },
            {
                "id": "past-1",
                "title": "終了済みイベント",
                "starts_at": "2026-08-01T12:00:00Z",
                "primary_action_url": "https://example.com/past",
            },
            {
                "id": "review-1",
                "title": "要レビューイベント",
                "starts_at": "2026-08-18T12:00:00Z",
                "review_required": True,
                "primary_action_url": "https://example.com/review",
            },
        ],
    }
    events = root / "events.json"
    events.write_text(json.dumps(payload), encoding="utf-8")

    first = render(events, root, "https://example.test/project")
    second = render(events, root, "https://example.test/project")

    assert first == second == {"event_count": 3, "indexable_count": 1, "sitemap_url_count": 2}
    detail = (root / "events/future-1/index.html").read_text(encoding="utf-8")
    assert "未来のVRChatイベント &lt;test&gt;" in detail
    assert "公式告知から観測した説明 &amp; 詳細" in detail
    assert 'rel="canonical" href="https://example.test/project/events/future-1/"' in detail
    assert 'data-track="official_link_click"' in detail
    assert "application/ld+json" not in detail
    assert not (root / "events/past-1").exists()
    assert not (root / "events/review-1").exists()

    sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://example.test/project/" in sitemap
    assert "https://example.test/project/events/future-1/" in sitemap
    assert "past-1" not in sitemap

    index = (root / "index.html").read_text(encoding="utf-8")
    assert index.count("searchable-events:start") == 1
    assert index.count('src="analytics.js"') == 1
    assert 'href="events/future-1/"' in index
    assert 'data-track="calendar_download"' in index


def test_render_requires_unique_indexable_ids(tmp_path: Path) -> None:
    root = _root(tmp_path)
    event = {
        "id": "same",
        "title": "イベント",
        "starts_at": "2026-08-17T12:00:00Z",
        "primary_action_url": "https://example.com/event",
    }
    events = root / "events.json"
    events.write_text(
        json.dumps({"generated_at": "2026-08-16T00:00:00Z", "events": [event, event]}),
        encoding="utf-8",
    )

    try:
        render(events, root, "https://example.test/project")
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate indexable event IDs must fail")
