from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def build_snapshot_identity(events_path: Path) -> dict[str, Any]:
    raw = events_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("events.json must contain an events list")

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

    return {
        "schema_version": 1,
        "events_sha256": hashlib.sha256(raw).hexdigest(),
        "event_count": len(events),
        "latest_event_id": latest_event_id,
        "latest_starts_at": latest_starts_at,
    }


def write_snapshot_identity(events_path: Path, output_path: Path) -> dict[str, Any]:
    snapshot = build_snapshot_identity(events_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot


def verify_snapshot_identity(events_path: Path, snapshot_path: Path) -> dict[str, Any]:
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    actual = build_snapshot_identity(events_path)
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        snapshot = verify_snapshot_identity(args.events, args.check)
        print(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
        return 0

    snapshot = write_snapshot_identity(args.events, args.output)
    print(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
