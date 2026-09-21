from __future__ import annotations

from scripts.validate_update_snapshot import OPTIONAL_COLLECTION_SOURCES, ROOT, require, sync_collection_health


def main() -> int:
    health = sync_collection_health(ROOT)
    statuses = {
        str(row.get("name")): str(row.get("status"))
        for row in health.get("sources", [])
        if isinstance(row, dict)
    }
    require(
        statuses.get("yahoo_realtime_events") == "ok",
        f"Yahoo collection is not healthy: {statuses.get('yahoo_realtime_events')}",
    )
    for name in OPTIONAL_COLLECTION_SOURCES:
        require(
            statuses.get(name) in {"ok", "degraded", "skipped"},
            f"optional collection source has invalid status: {name}={statuses.get(name)}",
        )
    print(f"collection health gate passed: {health.get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
