from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.render_search_pages import render as render_events
from scripts.render_series_pages import render as render_series


def _root(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(
        '<!doctype html><html><head><style>:root{--line:#ddd;--radius:20px;--muted:#666}.eyebrow{}</style></head>'
        '<body><a class="button" href="calendar.ics">カレンダーを購読</a><footer>footer</footer></body></html>',
        encoding="utf-8",
    )
    return tmp_path


def _entry(series_id: str, name: str, schedule_type: str = "recurring") -> dict[str, object]:
    return {
        "canonical_id": series_id,
        "canonical_name": name,
        "organizers": [f"{name}公式"],
        "category": "community",
        "schedule": {"type": schedule_type, "cadence": "毎週開催"},
        "introduction": f"{name}の公式説明です。",
        "participation_method": "公式Groupの案内に従ってJOIN。",
        "first_time_guide": "最新の公式案内を確認してください。",
        "highlights": ["定期開催", "公式Groupから参加"],
        "official_links": [
            {"label": "VRChat Group", "url": f"https://example.com/{series_id}", "kind": "vrchat_group"}
        ],
        "curation": {"status": "human_curated"},
    }


def test_series_pages_use_curated_identity_and_add_reverse_links(tmp_path: Path) -> None:
    root = _root(tmp_path)
    payload = {
        "generated_at": "2026-08-16T00:00:00Z",
        "events": [
            {
                "id": "series-1-a",
                "title": "毎週交流会 第1回",
                "canonical_name": "毎週交流会",
                "starts_at": "2026-08-17T12:00:00Z",
                "category": "community",
                "ontology_id": "weekly-social",
                "primary_action_url": "https://example.com/a",
            },
            {
                "id": "series-1-b",
                "title": "毎週交流会 第2回",
                "canonical_name": "毎週交流会",
                "starts_at": "2026-08-24T12:00:00Z",
                "category": "community",
                "ontology_id": "weekly-social",
                "primary_action_url": "https://example.com/b",
            },
            {
                "id": "thin-1",
                "title": "観測不足イベント",
                "starts_at": "2026-08-18T12:00:00Z",
                "category": "community",
                "ontology_id": "thin-series",
                "primary_action_url": "https://example.com/thin",
            },
        ],
    }
    ontology = {
        "entries": [
            _entry("weekly-social", "毎週交流会"),
            _entry("thin-series", "観測不足シリーズ"),
            _entry("irregular-series", "不定期シリーズ", "irregular"),
        ],
        "observed_entities": [
            {
                "entity_id": "weekly-social-official",
                "latest_observed_start": "2026-08-24T12:00:00Z",
                "matched_ontology_ids": {"weekly-social": 3},
            },
            {
                "entity_id": "thin-series-official",
                "latest_observed_start": "2026-08-18T12:00:00Z",
                "matched_ontology_ids": {"thin-series": 1},
            },
            {
                "entity_id": "irregular-series-official",
                "latest_observed_start": "2026-08-19T12:00:00Z",
                "matched_ontology_ids": {"irregular-series": 5},
            },
        ],
    }
    events_path = root / "events.json"
    ontology_path = root / "event-ontology.json"
    events_path.write_text(json.dumps(payload), encoding="utf-8")
    ontology_path.write_text(json.dumps(ontology), encoding="utf-8")

    render_events(events_path, root, "https://example.test/project")
    result = render_series(events_path, ontology_path, root, "https://example.test/project")

    assert result == {
        "series_count": 1,
        "series_event_links": 2,
        "event_series_reverse_links": 2,
        "series_observations": 3,
        "sitemap_url_count": 5,
    }
    page = (root / "series/weekly-social/index.html").read_text(encoding="utf-8")
    assert "毎週交流会 開催情報" in page
    assert 'rel="canonical" href="https://example.test/project/series/weekly-social/"' in page
    assert 'href="../../events/series-1-a/"' in page
    assert 'href="../../events/series-1-b/"' in page
    assert "観測3回" in page
    assert not (root / "series/thin-series").exists()
    assert not (root / "series/irregular-series").exists()

    detail = (root / "events/series-1-a/index.html").read_text(encoding="utf-8")
    assert 'href="../../series/weekly-social/"' in detail
    assert detail.count("series-link:start") == 1

    second = render_series(events_path, ontology_path, root, "https://example.test/project")
    detail = (root / "events/series-1-a/index.html").read_text(encoding="utf-8")
    assert second == result
    assert detail.count("series-link:start") == 1

    sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://example.test/project/series/weekly-social/" in sitemap
    assert "/series/thin-series/" not in sitemap


def test_ambiguous_observed_entity_fails_closed(tmp_path: Path) -> None:
    root = _root(tmp_path)
    payload = {
        "generated_at": "2026-08-16T00:00:00Z",
        "events": [
            {
                "id": "event-1",
                "title": "イベント",
                "starts_at": "2026-08-17T12:00:00Z",
                "category": "community",
                "ontology_id": "series-a",
                "primary_action_url": "https://example.com/event",
            }
        ],
    }
    ontology = {
        "entries": [_entry("series-a", "Series A"), _entry("series-b", "Series B")],
        "observed_entities": [
            {
                "entity_id": "ambiguous",
                "matched_ontology_ids": {"series-a": 2, "series-b": 1},
            }
        ],
    }
    events_path = root / "events.json"
    ontology_path = root / "event-ontology.json"
    events_path.write_text(json.dumps(payload), encoding="utf-8")
    ontology_path.write_text(json.dumps(ontology), encoding="utf-8")
    render_events(events_path, root, "https://example.test/project")

    with pytest.raises(ValueError, match="ambiguous ontology series matches"):
        render_series(events_path, ontology_path, root, "https://example.test/project")
