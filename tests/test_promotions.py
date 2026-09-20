from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_promotions import build_promotions


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_events() -> dict[str, object]:
    return {
        "generated_at": "2026-09-20T00:00:00Z",
        "events": [
            {
                "id": "event-1",
                "title": "Test Event",
                "starts_at": "2026-09-21T12:00:00Z",
                "category": "community",
                "primary_action_url": "https://example.com/event-1",
                "official_links": [
                    {"url": "https://example.com/event-1", "kind": "announcement"}
                ],
            }
        ],
    }


def promotion(status: str = "approved", destination: str = "https://example.com/event-1") -> dict[str, object]:
    return {
        "promotion_id": "promo-1",
        "campaign_id": "campaign-1",
        "event_id": "event-1",
        "type": "featured",
        "label": "Featured",
        "starts_at": "2026-09-20T00:00:00Z",
        "ends_at": "2026-09-27T00:00:00Z",
        "destination_url": destination,
        "placements": ["home", "tonight", "category"],
        "status": status,
    }


def test_build_promotions_projects_only_approved_metadata(tmp_path: Path) -> None:
    config = tmp_path / "promotions.json"
    events = tmp_path / "events.json"
    output = tmp_path / "public-promotions.json"
    source_js = tmp_path / "promotions.js"
    output_js = tmp_path / "public-promotions.js"

    write_json(config, {"schema_version": "1.0", "promotions": [promotion(), promotion("paused") | {"promotion_id": "promo-2", "campaign_id": "campaign-2"}]})
    write_json(events, canonical_events())
    source_js.write_text("console.log('promotion overlay');\n", encoding="utf-8")

    result = build_promotions(config, events, output, source_js, output_js)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == {"configured": 2, "approved": 1, "published": 1}
    assert payload["promotions"] == [promotion()]
    assert "title" not in payload["promotions"][0]
    assert "organizer" not in payload["promotions"][0]
    assert output_js.read_text(encoding="utf-8") == source_js.read_text(encoding="utf-8")


def test_build_promotions_rejects_noncanonical_destination(tmp_path: Path) -> None:
    config = tmp_path / "promotions.json"
    events = tmp_path / "events.json"
    output = tmp_path / "public-promotions.json"

    write_json(
        config,
        {
            "schema_version": "1.0",
            "promotions": [promotion(destination="https://evil.example/redirect")],
        },
    )
    write_json(events, canonical_events())

    with pytest.raises(ValueError, match="canonical event action URLs"):
        build_promotions(config, events, output)


def test_build_promotions_rejects_unknown_event(tmp_path: Path) -> None:
    config = tmp_path / "promotions.json"
    events = tmp_path / "events.json"
    output = tmp_path / "public-promotions.json"

    row = promotion() | {"event_id": "missing-event"}
    write_json(config, {"schema_version": "1.0", "promotions": [row]})
    write_json(events, canonical_events())

    with pytest.raises(ValueError, match="event_id not found"):
        build_promotions(config, events, output)


def test_build_promotions_rejects_invalid_window(tmp_path: Path) -> None:
    config = tmp_path / "promotions.json"
    events = tmp_path / "events.json"
    output = tmp_path / "public-promotions.json"

    row = promotion() | {
        "starts_at": "2026-09-27T00:00:00Z",
        "ends_at": "2026-09-20T00:00:00Z",
    }
    write_json(config, {"schema_version": "1.0", "promotions": [row]})
    write_json(events, canonical_events())

    with pytest.raises(ValueError, match="ends_at must be after"):
        build_promotions(config, events, output)


def test_promotion_client_has_expiry_disclosure_and_campaign_tracking() -> None:
    script = Path("web/promotions.js").read_text(encoding="utf-8")

    assert "now >= start" in script
    assert "now < end" in script
    assert "スポンサー掲載" in script
    assert "採否・分類には影響しません" in script
    assert "featured_event_click" in script
    assert "campaignId" in script
    assert "promotionType" in script
    assert "innerHTML" not in script
