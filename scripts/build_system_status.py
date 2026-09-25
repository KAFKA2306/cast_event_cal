from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.audit_freshness import DEFAULT_MAX_SNAPSHOT_AGE_MINUTES, audit, parse_instant, read_object
from scripts.validate_update_snapshot import OPTIONAL_COLLECTION_SOURCES, SOURCE_HEALTH_PATHS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HEALTH = ROOT / "public" / "health.json"
DEFAULT_SNAPSHOT = ROOT / "public" / "snapshot.json"
DEFAULT_OUTPUT = ROOT / "public" / "status.json"

VALID_HEALTH_STATUSES = {"ok", "degraded", "error"}
VALID_REFRESH_RESULTS = {"success", "failure", "cancelled", "skipped", "unknown"}


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_status(
    health: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    now: datetime,
    refresh_result: str,
    max_snapshot_age_minutes: int = DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
) -> dict[str, Any]:
    normalized_refresh_result = refresh_result.strip().lower()
    if normalized_refresh_result not in VALID_REFRESH_RESULTS:
        raise ValueError(f"unsupported refresh result: {refresh_result!r}")

    health_status = str(health.get("status") or "").strip().lower()
    if health_status not in VALID_HEALTH_STATUSES:
        raise ValueError(f"unsupported health status: {health_status!r}")

    snapshot_event_count = snapshot.get("event_count")
    if not isinstance(snapshot_event_count, int) or snapshot_event_count < 0:
        raise ValueError("snapshot event_count must be a non-negative integer")

    health_event_count = health.get("event_count")
    if isinstance(health_event_count, int) and health_event_count != snapshot_event_count:
        raise ValueError(
            "health/snapshot event count mismatch: "
            f"health={health_event_count} snapshot={snapshot_event_count}"
        )

    freshness = audit(
        health,
        snapshot,
        now=now,
        max_snapshot_age_minutes=max_snapshot_age_minutes,
    )

    if freshness["status"] != "ok":
        overall_status = "stale"
    elif normalized_refresh_result != "success" or health_status != "ok":
        overall_status = "degraded"
    else:
        overall_status = "ok"

    sources: list[dict[str, Any]] = []
    for source in health.get("sources", []):
        if not isinstance(source, dict):
            continue
        name = str(source.get("name") or "").strip()
        status = str(source.get("status") or "").strip().lower()
        if not name or not status:
            continue
        if name in OPTIONAL_COLLECTION_SOURCES:
            source_policy = "optional"
        elif name in SOURCE_HEALTH_PATHS:
            source_policy = "required"
        else:
            source_policy = "local"

        event_count = source.get("collection_event_count")
        if not isinstance(event_count, int):
            event_count = source.get("count") if isinstance(source.get("count"), int) else None

        sources.append(
            {
                "name": name,
                "status": status,
                "policy": source_policy,
                "last_observed_at": source.get("collection_generated_at"),
                "event_count": event_count,
            }
        )

    sources.sort(key=lambda row: row["name"])

    return {
        "schema_version": "1.0",
        "generated_at": isoformat_utc(now),
        "snapshot_generated_at": freshness["published_at"],
        "snapshot_age_minutes": freshness["snapshot_age_minutes"],
        "overall_status": overall_status,
        "refresh_result": normalized_refresh_result,
        "collection_status": health_status,
        "canonical_event_count": snapshot_event_count,
        "sources": sources,
        "slo": {
            "version": "production-refresh.v1",
            "max_snapshot_age_minutes": max_snapshot_age_minutes,
        },
        "freshness_reasons": freshness["reasons"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a durable public status projection from last-known-good calendar artifacts"
    )
    parser.add_argument("--health", type=Path, default=DEFAULT_HEALTH)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--refresh-result", default="unknown")
    parser.add_argument("--max-age-minutes", type=int, default=DEFAULT_MAX_SNAPSHOT_AGE_MINUTES)
    parser.add_argument("--now", help="fixed timezone-aware ISO-8601 instant for deterministic tests")
    args = parser.parse_args()

    now = parse_instant(args.now) if args.now else datetime.now(UTC)
    if now is None:
        raise ValueError("--now must be timezone-aware ISO-8601")

    status = build_status(
        read_object(args.health),
        read_object(args.snapshot),
        now=now,
        refresh_result=args.refresh_result,
        max_snapshot_age_minutes=args.max_age_minutes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "System status: "
        f"overall={status['overall_status']} "
        f"refresh={status['refresh_result']} "
        f"age_minutes={status['snapshot_age_minutes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
