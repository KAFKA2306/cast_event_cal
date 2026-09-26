from datetime import UTC, datetime

from scripts.build_system_status import build_status

NOW = datetime(2026, 9, 26, 2, 0, tzinfo=UTC)


def _snapshot():
    return {"event_count": 42, "generated_at": "2026-09-26T01:30:00Z"}


def test_ok_status_uses_same_freshness_contract():
    result = build_status({"status": "ok", "generated_at": "2026-09-26T01:30:00Z", "sources": []}, _snapshot(), now=NOW)
    assert result["overall_status"] == "ok"
    assert result["snapshot_age_minutes"] == 30.0
    assert result["canonical_event_count"] == 42
    assert result["slo"]["max_snapshot_age_minutes"] == 180


def test_optional_source_degradation_is_visible_without_becoming_stale():
    health = {
        "status": "degraded", "generated_at": "2026-09-26T01:30:00Z",
        "sources": [{"name": "optional", "status": "skipped", "count": 3,
                     "collection_generated_at": "2026-09-26T01:20:00Z", "reason": "secret detail"}],
    }
    result = build_status(health, _snapshot(), now=NOW)
    assert result["overall_status"] == "degraded"
    assert result["sources"] == [{"name": "optional", "status": "skipped", "last_observed_at": "2026-09-26T01:20:00Z", "event_count": 3}]
    assert "secret detail" not in str(result)


def test_stale_snapshot_overrides_healthy_collection():
    result = build_status(
        {"status": "ok", "generated_at": "2026-09-25T20:00:00Z", "sources": []},
        {"event_count": 42, "generated_at": "2026-09-25T20:00:00Z"}, now=NOW,
    )
    assert result["overall_status"] == "stale"
    assert result["snapshot_age_minutes"] == 360.0
