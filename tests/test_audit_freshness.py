from datetime import UTC, datetime

from scripts.audit_freshness import audit


def test_fresh_snapshot_passes_even_when_previous_health_is_stale():
    report = audit(
        {"status": "ok", "generated_at": "2026-09-20T00:00:00Z"},
        {"generated_at": "2026-09-22T00:00:00Z"},
        now=datetime(2026, 9, 22, 1, 0, tzinfo=UTC),
        max_snapshot_age_minutes=180,
    )
    assert report["status"] == "ok"
    assert report["snapshot_age_minutes"] == 60.0


def test_stale_snapshot_fails_closed_even_when_health_timestamp_is_fresh():
    report = audit(
        {"status": "ok", "generated_at": "2026-09-22T00:59:00Z"},
        {"generated_at": "2026-09-21T20:00:00Z"},
        now=datetime(2026, 9, 22, 1, 0, tzinfo=UTC),
        max_snapshot_age_minutes=180,
    )
    assert report["status"] == "stale"
    assert report["snapshot_age_minutes"] == 300.0
    assert "stale_public_snapshot" in report["reasons"]


def test_missing_snapshot_timestamp_fails_even_when_health_is_fresh():
    report = audit(
        {"status": "degraded", "generated_at": "2026-09-22T00:30:00Z"},
        {},
        now=datetime(2026, 9, 22, 1, 0, tzinfo=UTC),
        max_snapshot_age_minutes=180,
    )
    assert report["status"] == "stale"
    assert report["snapshot_age_minutes"] is None
    assert report["reasons"] == ["missing_publication_timestamp"]


def test_fresh_snapshot_is_not_stale_when_collection_health_is_degraded():
    report = audit(
        {"status": "degraded", "generated_at": "2026-09-20T00:00:00Z"},
        {"generated_at": "2026-09-22T11:30:00Z"},
        now=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        max_snapshot_age_minutes=180,
    )
    assert report["status"] == "ok"
    assert report["snapshot_age_minutes"] == 30.0
    assert report["reasons"] == []
