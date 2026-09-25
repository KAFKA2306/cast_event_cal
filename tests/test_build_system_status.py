from datetime import UTC, datetime

import pytest

from scripts.build_system_status import build_status


NOW = datetime(2026, 9, 26, 0, 0, tzinfo=UTC)


def make_health(
    *,
    status: str = "ok",
    generated_at: str = "2026-09-25T23:30:00Z",
    optional_status: str = "ok",
    event_count: int = 12,
) -> dict:
    return {
        "generated_at": generated_at,
        "status": status,
        "event_count": event_count,
        "sources": [
            {
                "name": "repository_manual_events",
                "status": "ok",
                "count": 5,
            },
            {
                "name": "yahoo_realtime_events",
                "status": "ok",
                "count": 4,
                "collection_generated_at": generated_at,
                "collection_event_count": 4,
            },
            {
                "name": "vrchat_calendar_discovery",
                "status": optional_status,
                "count": 3,
                "collection_generated_at": generated_at,
                "collection_event_count": 3,
                "reason": "secret-shaped text must not be projected",
            },
        ],
    }


def make_snapshot(*, event_count: int = 12) -> dict:
    return {
        "schema_version": 1,
        "event_count": event_count,
        "events_sha256": "abc123",
    }


def test_fresh_healthy_refresh_is_ok() -> None:
    status = build_status(
        make_health(),
        make_snapshot(),
        now=NOW,
        refresh_result="success",
        max_snapshot_age_minutes=180,
    )

    assert status["overall_status"] == "ok"
    assert status["snapshot_age_minutes"] == 30.0
    assert status["canonical_event_count"] == 12
    assert status["slo"] == {
        "version": "production-refresh.v1",
        "max_snapshot_age_minutes": 180,
    }


def test_optional_source_degradation_is_durable_without_reason_leakage() -> None:
    status = build_status(
        make_health(status="degraded", optional_status="skipped"),
        make_snapshot(),
        now=NOW,
        refresh_result="success",
        max_snapshot_age_minutes=180,
    )

    assert status["overall_status"] == "degraded"
    optional = next(row for row in status["sources"] if row["name"] == "vrchat_calendar_discovery")
    assert optional["policy"] == "optional"
    assert optional["status"] == "skipped"
    assert "reason" not in optional


def test_failed_refresh_marks_fresh_last_known_good_snapshot_degraded() -> None:
    status = build_status(
        make_health(),
        make_snapshot(),
        now=NOW,
        refresh_result="failure",
        max_snapshot_age_minutes=180,
    )

    assert status["overall_status"] == "degraded"
    assert status["refresh_result"] == "failure"
    assert status["freshness_reasons"] == []


def test_stale_snapshot_takes_precedence_over_collection_and_refresh_state() -> None:
    status = build_status(
        make_health(generated_at="2026-09-25T18:00:00Z"),
        make_snapshot(),
        now=NOW,
        refresh_result="failure",
        max_snapshot_age_minutes=180,
    )

    assert status["overall_status"] == "stale"
    assert status["snapshot_age_minutes"] == 360.0
    assert status["freshness_reasons"] == ["stale_public_snapshot"]


def test_event_count_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="event count mismatch"):
        build_status(
            make_health(event_count=12),
            make_snapshot(event_count=11),
            now=NOW,
            refresh_result="success",
        )


def test_same_inputs_produce_same_status() -> None:
    first = build_status(
        make_health(),
        make_snapshot(),
        now=NOW,
        refresh_result="success",
    )
    second = build_status(
        make_health(),
        make_snapshot(),
        now=NOW,
        refresh_result="success",
    )

    assert first == second
