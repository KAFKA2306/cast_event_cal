from __future__ import annotations

import json
from pathlib import Path

from scripts.render_category_pages import render as render_categories
from scripts.render_search_pages import render as render_events


def _root(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(
        '<!doctype html><html><head><style>:root{--line:#ddd;--radius:20px;--muted:#666}.eyebrow{}</style></head>'
        '<body><a class="button" href="calendar.ics">カレンダーを購読</a><footer>footer</footer></body></html>',
        encoding="utf-8",
    )
    return tmp_path


def test_category_pages_use_only_indexable_observed_events(tmp_path: Path) -> None:
    root = _root(tmp_path)
    payload = {
        "generated_at": "2026-08-16T00:00:00Z",
        "events": [
            {
                "id": "music-1",
                "title": "音楽イベント",
                "starts_at": "2026-08-17T12:00:00Z",
                "category": "music",
                "primary_action_url": "https://example.com/music",
                "primary_action_kind": "announcement",
            },
            {
                "id": "community-1",
                "title": "交流イベント",
                "starts_at": "2026-08-18T12:00:00Z",
                "category": "community",
                "primary_action_url": "https://example.com/community",
                "primary_action_kind": "join_group",
            },
            {
                "id": "other-1",
                "title": "その他",
                "starts_at": "2026-08-19T12:00:00Z",
                "category": "other",
                "primary_action_url": "https://example.com/other",
            },
            {
                "id": "review-1",
                "title": "要レビュー",
                "starts_at": "2026-08-20T12:00:00Z",
                "category": "music",
                "review_required": True,
                "primary_action_url": "https://example.com/review",
            },
        ],
    }
    ontology = {
        "categories": [
            {"id": "music", "label": "音楽・ダンス", "priority": 90},
            {"id": "community", "label": "交流・カフェ", "priority": 60},
            {"id": "art", "label": "アート・展示・撮影", "priority": 95},
            {"id": "other", "label": "その他", "priority": 0},
        ]
    }
    events_path = root / "events.json"
    ontology_path = root / "category-ontology.json"
    events_path.write_text(json.dumps(payload), encoding="utf-8")
    ontology_path.write_text(json.dumps(ontology), encoding="utf-8")

    render_events(events_path, root, "https://example.test/project")
    result = render_categories(events_path, ontology_path, root, "https://example.test/project")

    assert result == {"category_count": 2, "category_event_links": 2, "sitemap_url_count": 6}
    music = (root / "categories/music/index.html").read_text(encoding="utf-8")
    community = (root / "categories/community/index.html").read_text(encoding="utf-8")
    assert "VRChat 音楽・ダンスイベント一覧" in music
    assert 'rel="canonical" href="https://example.test/project/categories/music/"' in music
    assert 'href="../../events/music-1/"' in music
    assert "要レビュー" not in music
    assert "参加情報: 公式告知 1件" in music
    assert 'href="../../events/community-1/"' in community
    assert "参加情報: 参加方法 1件" in community
    assert not (root / "categories/art").exists()
    assert not (root / "categories/other").exists()

    sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://example.test/project/categories/music/" in sitemap
    assert "https://example.test/project/categories/community/" in sitemap
    assert "/categories/art/" not in sitemap
    assert "/categories/other/" not in sitemap
