#!/usr/bin/env python3
"""Inventory public/events.json and fail closed on consumer-breaking schema drift."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

CONSUMERS: dict[str, tuple[str, ...]] = {
    "identity": ("id",),
    "tonight": ("id", "title", "starts_at"),
    "calendar": ("id", "title", "starts_at"),
    "atom": ("id", "title", "starts_at"),
    "detail": ("id", "title", "starts_at"),
}
REQUIRED = frozenset({"id", "title", "starts_at"})


def _kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _events(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("events"), list):
        rows = payload["events"]
    else:
        raise ValueError("public events payload must be a list or an object with events[]")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("every public event must be an object")
    return rows


def inventory(payload: Any) -> dict[str, Any]:
    rows = _events(payload)
    fields: dict[str, Counter[str]] = defaultdict(Counter)
    present: Counter[str] = Counter()
    for row in rows:
        for name, value in row.items():
            present[name] += 1
            fields[name][_kind(value)] += 1
    total = len(rows)
    schema = {}
    for name in sorted(fields):
        schema[name] = {
            "types": dict(sorted(fields[name].items())),
            "present": present[name],
            "missing": total - present[name],
            "nullable": fields[name]["null"] > 0,
            "requiredByConsumer": sorted(k for k, values in CONSUMERS.items() if name in values),
        }
    identity = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"schemaVersion": 1, "eventCount": total, "snapshotIdentity": identity, "fields": schema}


def verify(report: dict[str, Any]) -> list[dict[str, Any]]:
    fields = report["fields"]
    failures = []
    for name in sorted(REQUIRED):
        info = fields.get(name)
        affected = sorted(k for k, values in CONSUMERS.items() if name in values)
        if info is None:
            failures.append({"field": name, "reason": "required_field_missing", "affectedConsumers": affected})
            continue
        if info["missing"]:
            failures.append({"field": name, "reason": "required_field_missing_on_records", "count": info["missing"], "affectedConsumers": affected})
        non_null_types = set(info["types"]) - {"null"}
        if non_null_types != {"string"}:
            failures.append({"field": name, "reason": "required_field_type_drift", "types": sorted(non_null_types), "affectedConsumers": affected})
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="public/events.json")
    parser.add_argument("--output", default="artifacts/public-event-schema.json")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = inventory(payload)
    report["breakingCandidates"] = verify(report)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"eventCount": report["eventCount"], "fieldCount": len(report["fields"]), "breakingCandidates": len(report["breakingCandidates"])}))
    return 1 if report["breakingCandidates"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
