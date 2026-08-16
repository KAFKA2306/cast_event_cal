from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.render_category_pages import render as render_categories
from scripts.render_internal_links import render as render_links
from scripts.render_search_pages import render as render_events
from scripts.render_series_pages import render as render_series
from scripts.verify_crawl_graph import verify


def _root(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(
        '<!doctype html><html><head><style>:root{--line:#ddd;--radius:20px;--muted:#666}.eyebrow{}</style></head>'
        '<body><a class="button" href="calendar.ics">カレンダーを購読</a><footer>footer</footer></body></html>',
        encoding="utf-8",
    )
    return tmp_path


def _build_surface(tmp_path: Path) -> Path:
    root = _root(tmp_path)
    payload = {
        "generated_at": "2026-08-16T00:00:00Z",
        "events": [
            {
                "id": "social-1",
                "title": "交流会 1",
                "canonical_name": "毎週交流会",
                "starts_at": "2026-08-17T12:00:00Z",
                "category": "community",
                "category_label": "交流・カフェ",
                "ontology_id": "weekly-social",
                "primary_action_url": "https://example.com/social-1",
            },
            {
                "id": "social-2",
                "title": "交流会 2",
                "canonical_name": "毎週交流会",
                "starts_at": "2026-08-24T12:00:00Z",
                "category": "community",
                "category_label": "交流・カフェ",
                "ontology_id": "weekly-social",
                "primary_action_url": "https://example.com/social-2",
            },
            {
                "id": "music-1",
                "title": "音楽イベント",
                "starts_at": "2026-08-18T12:00:00Z",
                "category": "music",
                "category_label": "音楽・ダンス",
                "primary_action_url": "https://example.com/music-1",
            },
        ],
    }
    category_ontology = {
        "categories": [
            {"id": "community", "label": "交流・カフェ", "priority": 60},
            {"id": "music", "label": "音楽・ダンス", "priority": 90},
            {"id": "other", "label": "その他", "priority": 0},
        ]
    }
    event_ontology = {
        "entries": [
            {
                "canonical_id": "weekly-social",
                "canonical_name": "毎週交流会",
                "organizers": ["交流会公式"],
                "category": "community",
                "schedule": {"type": "recurring", "cadence": "毎週開催"},
                "introduction": "毎週の交流イベントです。",
                "participation_method": "公式Groupから参加。",
                "first_time_guide": "公式案内を確認してください。",
                "highlights": ["定期開催"],
                "official_links": [
                    {"label": "VRChat Group", "url": "https://example.com/group", "kind": "vrchat_group"}
                ],
                "curation": {"status": "human_curated"},
            }
        ],
        "observed_entities": [
            {
                "entity_id": "weekly-social-official",
                "latest_observed_start": "2026-08-24T12:00:00Z",
                "matched_ontology_ids": {"weekly-social": 2},
            }
        ],
    }
    events_path = root / "events.json"
    category_path = root / "category-ontology.json"
    ontology_path = root / "event-ontology.json"
    events_path.write_text(json.dumps(payload), encoding="utf-8")
    category_path.write_text(json.dumps(category_ontology), encoding="utf-8")
    ontology_path.write_text(json.dumps(event_ontology), encoding="utf-8")

    base = "https://example.test/project"
    render_events(events_path, root, base)
    render_categories(events_path, category_path, root, base)
    render_series(events_path, ontology_path, root, base)
    render_links(root)
    return root


def test_crawl_graph_has_zero_orphans_and_static_hub_links(tmp_path: Path) -> None:
    root = _build_surface(tmp_path)
    result = verify(root, "https://example.test/project")

    assert result["page_count"] == 7
    assert result["event_page_count"] == 3
    assert result["orphan_count"] == 0
    assert result["broken_search_link_count"] == 0
    assert result["unreachable_count"] == 0
    assert result["event_pages_without_inbound"] == 0
    assert result["max_depth"] == 1

    index = (root / "index.html").read_text(encoding="utf-8")
    assert 'href="categories/community/"' in index
    assert 'href="series/weekly-social/"' in index
    detail = (root / "events/social-1/index.html").read_text(encoding="utf-8")
    assert 'href="../../categories/community/"' in detail
    assert 'href="../social-2/"' in detail
    assert 'href="../../series/weekly-social/"' in detail


def test_crawl_graph_rejects_broken_search_link(tmp_path: Path) -> None:
    root = _build_surface(tmp_path)
    index = root / "index.html"
    text = index.read_text(encoding="utf-8")
    index.write_text(text.replace("<footer>", '<a href="events/missing/">broken</a><footer>', 1), encoding="utf-8")

    with pytest.raises(ValueError, match="broken/non-canonical search links"):
        verify(root, "https://example.test/project")


def test_crawl_graph_rejects_orphan_page(tmp_path: Path) -> None:
    root = _root(tmp_path)
    (root / "events/orphan").mkdir(parents=True)
    (root / "events/orphan/index.html").write_text("<!doctype html><p>orphan</p>", encoding="utf-8")
    (root / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        '<url><loc>https://example.test/project/</loc></url>'
        '<url><loc>https://example.test/project/events/orphan/</loc></url>'
        '</urlset>',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="orphan indexable pages"):
        verify(root, "https://example.test/project")
