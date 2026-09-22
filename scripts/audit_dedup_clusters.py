from __future__ import annotations

import argparse
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from scripts.deduplicate_occurrences import event_ordinal, occurrence_match

DEFAULT_EVENTS = Path("public/events.json")
DEFAULT_REPORT = Path("public/event-dedup-safety-audit.json")


def audit(events: list[dict[str, Any]]) -> dict[str, Any]:
    parent = list(range(len(events)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_start: dict[str, list[int]] = defaultdict(list)
    for i, event in enumerate(events):
        by_start[str(event.get("starts_at") or "")].append(i)

    edges: list[dict[str, Any]] = []
    for indexes in by_start.values():
        for a, b in combinations(indexes, 2):
            match = occurrence_match(events[a], events[b])
            if match:
                reason, confidence = match
                union(a, b)
                edges.append({"left": a, "right": b, "reason": reason, "confidence": confidence})

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(events)):
        groups[find(i)].append(i)

    unsafe: list[dict[str, Any]] = []
    for indexes in groups.values():
        if len(indexes) < 2:
            continue
        ordinals = sorted({value for i in indexes if (value := event_ordinal(events[i]))})
        existing_ids = sorted({str(events[i].get("occurrence_id") or "") for i in indexes if events[i].get("occurrence_id")})
        if len(ordinals) <= 1 and len(existing_ids) <= 1:
            continue
        member_set = set(indexes)
        unsafe.append({
            "member_ids": sorted(str(events[i].get("id") or "") for i in indexes),
            "starts_at": str(events[indexes[0]].get("starts_at") or ""),
            "ordinals": ordinals,
            "existing_occurrence_ids": existing_ids,
            "edges": [edge for edge in edges if edge["left"] in member_set and edge["right"] in member_set],
        })

    return {
        "schema_version": "1.0",
        "policy_version": "dedup-cluster-safety.v1",
        "event_count": len(events),
        "matched_edge_count": len(edges),
        "unsafe_cluster_count": len(unsafe),
        "unsafe_clusters": unsafe,
        "status": "ok" if not unsafe else "unsafe",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail closed on contradictory transitive dedup clusters")
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    document = json.loads(args.events.read_text(encoding="utf-8"))
    events = document.get("events", [])
    if not isinstance(events, list):
        raise ValueError("events document must contain an events array")
    report = audit([row for row in events if isinstance(row, dict)])
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"dedup safety audit: status={report['status']} unsafe_clusters={report['unsafe_cluster_count']}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
