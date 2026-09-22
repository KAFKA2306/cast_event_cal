from datetime import UTC, datetime

from scripts.audit_freshness import audit


def test_fresh_snapshot_passes():
    report = audit(
        {"status": "ok", "generated_at": "2026-09-22T00:00:00Z"},
        {"generated_at": "2026-09-22T00:00:00Z"},
        now=datetime(2026, 9, 22, 1, 0, tzinfo=UTC),
        max_snapshot_age_minutes=180,
    )
    assert report["status"] == "ok"
    assert report["snapshot_age_minutes"] == 60.0


def test_stale_snapshot_fails_closed():
    report = audit(
        {"status": "ok", "generated_at": "2026-09-21T20:00:00Z"},
        {"generated_at": "2026-09-21T20:00:00Z"},
        now=datetime(2026, 9, 22, 1, 0, tzinfo=UTC),
        max_snapshot_age_minutes=180,
    )
    assert report["status"] == "stale"
    assert "stale_public_snapshot" in report["reasons"]


def test_missing_timestamp_is_unknown_and_fails():
    report = audit(
        {"status": "ok"},
        {},
        now=datetime(2026, 9, 22, 1, 0, tzinfo=UTC),
        max_snapshot_age_minutes=180,
    )
    assert report["status"] == "stale"
    assert report["snapshot_age_minutes"] is None
    assert report["reasons"] == ["missing_publication_timestamp"]
