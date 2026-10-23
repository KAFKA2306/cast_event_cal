from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def build_snapshot_identity(
    events_path: Path, source_revision: str | None = None
) -> dict[str, Any]:
    raw = events_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("events.json must contain an events list")

    timestamp = payload.get("generated_at")
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise ValueError("events.json must contain a generated_at timestamp")
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("events.json generated_at must be ISO-8601") from exc
    if parsed_timestamp.tzinfo is None:
        raise ValueError("events.json generated_at must include a timezone")

    count = payload.get("count")
    if count != len(events):
        raise ValueError(f"events.json count mismatch: count={count!r} actual={len(events)}")

    latest = max(
        events,
        key=lambda row: (
            str(row.get("starts_at") or ""),
            str(row.get("id") or row.get("source_id") or ""),
        ),
        default={},
    )
    latest_event_id = str(latest.get("id") or latest.get("source_id") or "")
    latest_starts_at = str(latest.get("starts_at") or "")

    result: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": timestamp,
        "events_sha256": hashlib.sha256(raw).hexdigest(),
        "event_count": len(events),
        "latest_event_id": latest_event_id,
        "latest_starts_at": latest_starts_at,
    }
    if source_revision is not None:
        source_revision = source_revision.strip()
        if not source_revision:
            raise ValueError("source_revision must not be empty")
        result["source_revision"] = source_revision
    return result


def write_snapshot_identity(
    events_path: Path, output_path: Path, source_revision: str | None = None
) -> dict[str, Any]:
    snapshot = build_snapshot_identity(events_path, source_revision)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot


def verify_snapshot_identity(
    events_path: Path, snapshot_path: Path, source_revision: str | None = None
) -> dict[str, Any]:
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if source_revision is None and "source_revision" in expected:
        source_revision = expected["source_revision"]
    actual = build_snapshot_identity(events_path, source_revision)
    if expected != actual:
        raise ValueError(
            "snapshot identity mismatch:\n"
            f"expected={json.dumps(expected, ensure_ascii=False, sort_keys=True)}\n"
            f"actual={json.dumps(actual, ensure_ascii=False, sort_keys=True)}"
        )
    return actual


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write or verify the deterministic identity of public/events.json."
    )
    parser.add_argument("--events", type=Path, default=Path("public/events.json"))
    parser.add_argument("--output", type=Path, default=Path("public/snapshot.json"))
    parser.add_argument("--check", type=Path)
    parser.add_argument("--source-revision", type=str)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        snapshot = verify_snapshot_identity(args.events, args.check, args.source_revision)
        print(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
        return 0

    snapshot = write_snapshot_identity(args.events, args.output, args.source_revision)
    print(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
