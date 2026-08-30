import json
from datetime import UTC, datetime, timedelta

import pytest

from scripts.validate_update_snapshot import SnapshotValidationError, sync_collection_health


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def base_public_health():
    return {
        "schema_version": "1.0",
        "status": "ok",
        "enabled_sources": 5,
        "successful_sources": 5,
        "failed_sources": 0,
        "event_count": 3,
        "sources": [
            {"name": "repository_manual_events", "status": "ok", "count": 1},
            {"name": "vrchat_calendar_discovery", "status": "ok", "count": 0},
            {"name": "x_curated_events", "status": "ok", "count": 1},
            {"name": "yahoo_realtime_events", "status": "ok", "count": 1},
            {"name": "external_calendar_events", "status": "ok", "count": 0},
        ],
    }


def write_sidecars(root, generated_at):
    write_json(
        root / "data/discovery_health.json",
        {"status": "skipped", "generated_at": generated_at, "reason": "credential not configured", "event_count": 0},
    )
    write_json(
        root / "data/x_discovery_health.json",
        {"status": "skipped", "generated_at": generated_at, "reason": "token not configured", "event_count": 1},
    )
    write_json(
        root / "data/yahoo_realtime_health.json",
        {"status": "ok", "generated_at": generated_at, "event_count": 1},
    )
    write_json(
        root / "data/external_discovery_health.json",
        {"status": "ok", "generated_at": generated_at, "event_count": 0},
    )


def test_sync_collection_health_preserves_skipped_sources(tmp_path):
    now = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    generated_at = "2026-08-30T11:30:00Z"
    write_json(tmp_path / "public/health.json", base_public_health())
    write_sidecars(tmp_path, generated_at)

    health = sync_collection_health(tmp_path, now=now)
    statuses = {row["name"]: row["status"] for row in health["sources"]}

    assert statuses["vrchat_calendar_discovery"] == "skipped"
    assert statuses["x_curated_events"] == "skipped"
    assert statuses["yahoo_realtime_events"] == "ok"
    assert health["status"] == "degraded"
    assert health["skipped_sources"] == 2
    assert health["failed_sources"] == 0


def test_sync_collection_health_rejects_stale_sidecar(tmp_path):
    now = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    write_json(tmp_path / "public/health.json", base_public_health())
    write_sidecars(tmp_path, "2026-08-30T08:00:00Z")

    with pytest.raises(SnapshotValidationError, match="stale"):
        sync_collection_health(tmp_path, now=now, max_age=timedelta(hours=2))


def test_sync_collection_health_keeps_degraded_source_visible(tmp_path):
    now = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    generated_at = "2026-08-30T11:30:00Z"
    write_json(tmp_path / "public/health.json", base_public_health())
    write_sidecars(tmp_path, generated_at)
    write_json(
        tmp_path / "data/x_discovery_health.json",
        {"status": "degraded", "generated_at": generated_at, "reason": "API request failed", "event_count": 1},
    )

    health = sync_collection_health(tmp_path, now=now)
    statuses = {row["name"]: row["status"] for row in health["sources"]}

    assert statuses["x_curated_events"] == "degraded"
    assert health["status"] == "degraded"
    assert health["degraded_sources"] == 1
