from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CALENDAR_HEALTH = Path("public/health.json")
EVENTS = Path("public/events.json")
YAHOO_HEALTH = Path("data/yahoo_realtime_health.json")
OUTPUT = Path("public/registration-count-audit.json")
KPI_LOG = Path("public/accepted-event-kpi.jsonl")
MAX_SNAPSHOTS = 90


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def integer(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not a count")
    return int(value)


def snapshot(
    calendar: dict[str, Any], yahoo: dict[str, Any], events: dict[str, Any]
) -> dict[str, Any]:
    sources = {
        str(row.get("name")): integer(row.get("count", 0))
        for row in calendar.get("sources", [])
        if isinstance(row, dict) and row.get("name")
    }
    published_count = integer(events["count"])
    rows = events.get("events")
    if not isinstance(rows, list) or published_count != len(rows):
        raise ValueError("public events count must match the events array")
    return {
        "generated_at": str(events.get("generated_at") or calendar["generated_at"]),
        "calendar_event_count": published_count,
        "normalized_event_count": integer(calendar["event_count"]),
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
    events = read_json(EVENTS, {})
    yahoo = read_json(YAHOO_HEALTH, {})
    if calendar.get("status") != "ok":
        raise ValueError("calendar health must be ok")
    if yahoo.get("status") != "ok":
        raise ValueError("Yahoo health must be ok")
    if not isinstance(events, dict) or "count" not in events:
        raise ValueError("public events snapshot is required")

    current = snapshot(calendar, yahoo, events)
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


def read_kpi_log(path: Path = KPI_LOG) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError(f"KPI log line {line_number} must be an object")
        rows.append(row)
    return rows


def append_kpi_log(latest: dict[str, Any], path: Path = KPI_LOG) -> dict[str, Any]:
    generated_at = str(latest["generated_at"])
    accepted = integer(latest["yahoo_accepted_count"])
    rows = read_kpi_log(path)

    if rows and rows[-1].get("generated_at") == generated_at:
        return rows[-1]

    previous = rows[-1] if rows else None
    previous_accepted = integer(previous["accepted_event_cumulative"]) if previous else None
    if previous_accepted is not None and accepted < previous_accepted:
        raise ValueError(
            "accepted-event cumulative KPI must not decrease: "
            f"{previous_accepted} -> {accepted}"
        )

    row = {
        "generated_at": generated_at,
        "accepted_event_cumulative": accepted,
        "delta": None if previous_accepted is None else accepted - previous_accepted,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return row


def main() -> int:
    payload = build()
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    kpi = append_kpi_log(payload["latest"])
    print(json.dumps({"latest": payload["latest"], "kpi": kpi}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
