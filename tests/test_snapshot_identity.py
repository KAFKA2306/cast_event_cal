import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.audit_freshness import audit
from scripts.write_snapshot_identity import (
    build_snapshot_identity,
    verify_snapshot_identity,
    write_snapshot_identity,
)


def write_events(path: Path, events: list[dict[str, str]], *, count: int | None = None, generated_at: str | None = "2026-09-22T00:00:00Z") -> bytes:
    payload = {
        "count": len(events) if count is None else count,
        "events": events,
        "generated_at": generated_at,
    }
    raw = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return raw


def test_build_snapshot_identity_is_deterministic(tmp_path: Path) -> None:
    events_path = tmp_path / "events.json"
    raw = write_events(
        events_path,
        [
            {"id": "early", "starts_at": "2026-09-20T10:00:00Z"},
            {"id": "late", "starts_at": "2026-09-21T10:00:00Z"},
        ],
    )

    snapshot = build_snapshot_identity(events_path)

    assert snapshot == {
        "schema_version": 1,
        "generated_at": "2026-09-22T00:00:00Z",
        "events_sha256": hashlib.sha256(raw).hexdigest(),
        "event_count": 2,
        "latest_event_id": "late",
        "latest_starts_at": "2026-09-21T10:00:00Z",
    }


def test_write_and_verify_snapshot_identity(tmp_path: Path) -> None:
    events_path = tmp_path / "events.json"
    snapshot_path = tmp_path / "snapshot.json"
    write_events(events_path, [{"id": "event-1", "starts_at": "2026-09-20T12:00:00Z"}])

    written = write_snapshot_identity(events_path, snapshot_path)

    assert verify_snapshot_identity(events_path, snapshot_path) == written


def test_verify_snapshot_identity_rejects_stale_snapshot(tmp_path: Path) -> None:
    events_path = tmp_path / "events.json"
    snapshot_path = tmp_path / "snapshot.json"
    write_events(events_path, [{"id": "event-1", "starts_at": "2026-09-20T12:00:00Z"}])
    write_snapshot_identity(events_path, snapshot_path)
    write_events(events_path, [{"id": "event-2", "starts_at": "2026-09-21T12:00:00Z"}])

    with pytest.raises(ValueError, match="snapshot identity mismatch"):
        verify_snapshot_identity(events_path, snapshot_path)


def test_build_snapshot_identity_rejects_count_mismatch(tmp_path: Path) -> None:
    events_path = tmp_path / "events.json"
    write_events(events_path, [{"id": "event-1", "starts_at": "2026-09-20T12:00:00Z"}], count=2)

    with pytest.raises(ValueError, match="count mismatch"):
        build_snapshot_identity(events_path)


@pytest.mark.parametrize("generated_at", [None, "not-a-timestamp", "2026-09-22T00:00:00"])
def test_snapshot_identity_rejects_missing_or_invalid_timestamp(tmp_path: Path, generated_at: str | None) -> None:
    events_path = tmp_path / "events.json"
    write_events(events_path, [{"id": "event-1", "starts_at": "2026-09-20T12:00:00Z"}], generated_at=generated_at)
    with pytest.raises(ValueError, match="generated_at"):
        build_snapshot_identity(events_path)


def test_generated_identity_drives_freshness_not_health(tmp_path: Path) -> None:
    events_path = tmp_path / "events.json"
    write_events(events_path, [{"id": "event-1", "starts_at": "2026-09-20T12:00:00Z"}])
    snapshot = build_snapshot_identity(events_path)
    report = audit(
        {"generated_at": "2026-09-20T00:00:00Z", "status": "degraded"},
        snapshot,
        now=datetime(2026, 9, 22, 1, 0, tzinfo=UTC),
        max_snapshot_age_minutes=180,
    )
    assert report["status"] == "ok"
    assert report["published_at"] == "2026-09-22T00:00:00Z"
    assert report["snapshot_age_minutes"] == 60.0
