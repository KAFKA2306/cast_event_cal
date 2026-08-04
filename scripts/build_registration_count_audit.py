from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CALENDAR_HEALTH = Path("public/health.json")
YAHOO_HEALTH = Path("data/yahoo_realtime_health.json")
OUTPUT = Path("public/registration-count-audit.json")
MAX_SNAPSHOTS = 90


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def integer(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not a count")
    return int(value)


def snapshot(calendar: dict[str, Any], yahoo: dict[str, Any]) -> dict[str, Any]:
    sources = {
        str(row.get("name")): integer(row.get("count", 0))
        for row in calendar.get("sources", [])
        if isinstance(row, dict) and row.get("name")
    }
    return {
        "generated_at": str(calendar["generated_at"]),
        "calendar_event_count": integer(calendar["event_count"]),
        "source_counts": sources,
        "yahoo_candidate_count": integer(yahoo["history_candidate_count"]),
        "yahoo_accepted_count": integer(yahoo["history_accepted_count"]),
        "yahoo_rejected_count": integer(yahoo["history_rejected_count"]),
        "yahoo_unique_candidates_this_run": integer(yahoo.get("unique_candidates_this_run", 0)),
        "yahoo_queries_succeeded": integer(yahoo.get("queries_succeeded", 0)),
        "yahoo_queries_failed": integer(yahoo.get("queries_failed", 0)),
    }


def delta(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any] | None:
    if previous is None:
        return None
    source_names = sorted(set(previous.get("source_counts", {})) | set(current.get("source_counts", {})))
    return {
        "from_generated_at": previous["generated_at"],
        "calendar_event_count": current["calendar_event_count"] - previous["calendar_event_count"],
        "source_counts": {
            name: current.get("source_counts", {}).get(name, 0)
            - previous.get("source_counts", {}).get(name, 0)
            for name in source_names
        },
        "yahoo_candidate_count": current["yahoo_candidate_count"] - previous["yahoo_candidate_count"],
        "yahoo_accepted_count": current["yahoo_accepted_count"] - previous["yahoo_accepted_count"],
        "yahoo_rejected_count": current["yahoo_rejected_count"] - previous["yahoo_rejected_count"],
    }


def build() -> dict[str, Any]:
    calendar = read_json(CALENDAR_HEALTH, {})
    yahoo = read_json(YAHOO_HEALTH, {})
    if calendar.get("status") != "ok":
        raise ValueError("calendar health must be ok")
    if yahoo.get("status") != "ok":
        raise ValueError("Yahoo health must be ok")

    current = snapshot(calendar, yahoo)
    existing = read_json(OUTPUT, {})
    snapshots = [row for row in existing.get("snapshots", []) if isinstance(row, dict)]
    snapshots = [row for row in snapshots if row.get("generated_at") != current["generated_at"]]
    previous = snapshots[-1] if snapshots else None
    current["delta_from_previous"] = delta(current, previous)
    snapshots.append(current)
    snapshots = snapshots[-MAX_SNAPSHOTS:]

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "ok",
        "snapshot_count": len(snapshots),
        "latest": current,
        "snapshots": snapshots,
    }


def main() -> int:
    payload = build()
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["latest"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
