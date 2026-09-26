from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.audit_freshness import DEFAULT_MAX_SNAPSHOT_AGE_MINUTES, audit, read_object

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HEALTH = ROOT / "public" / "health.json"
DEFAULT_SNAPSHOT = ROOT / "public" / "snapshot.json"
DEFAULT_OUTPUT = ROOT / "public" / "status.json"


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else None


def build_status(
    health: dict[str, Any], snapshot: dict[str, Any], *, now: datetime,
    max_snapshot_age_minutes: int = DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
) -> dict[str, Any]:
    freshness = audit(health, snapshot, now=now, max_snapshot_age_minutes=max_snapshot_age_minutes)
    source_rows: list[dict[str, Any]] = []
    for source in health.get("sources", []):
        if not isinstance(source, dict) or not isinstance(source.get("name"), str):
            continue
        observed = source.get("collection_generated_at")
        source_rows.append({
            "name": source["name"],
            "status": source.get("status", "unknown"),
            "last_observed_at": observed if _instant(observed) else None,
            "event_count": source.get("count") if isinstance(source.get("count"), int) else None,
        })

    health_status = health.get("status")
    if freshness["status"] == "stale":
        overall = "stale"
    elif health_status == "ok":
        overall = "ok"
    else:
        overall = "degraded"

    return {
        "schema_version": "1.0",
        "generated_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "snapshot_generated_at": freshness["published_at"],
        "snapshot_age_minutes": freshness["snapshot_age_minutes"],
        "overall_status": overall,
        "canonical_event_count": snapshot.get("event_count"),
        "sources": source_rows,
        "slo": {"max_snapshot_age_minutes": max_snapshot_age_minutes, "version": "1.0"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a durable public system-health projection")
    parser.add_argument("--health", type=Path, default=DEFAULT_HEALTH)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-age-minutes", type=int, default=DEFAULT_MAX_SNAPSHOT_AGE_MINUTES)
    parser.add_argument("--now", help="fixed timezone-aware ISO-8601 instant")
    args = parser.parse_args()
    now = _instant(args.now) if args.now else datetime.now(UTC)
    if now is None:
        raise ValueError("--now must be timezone-aware ISO-8601")
    status = build_status(read_object(args.health), read_object(args.snapshot), now=now,
                          max_snapshot_age_minutes=args.max_age_minutes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"System status: {status['overall_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
