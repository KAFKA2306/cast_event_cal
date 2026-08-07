from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

API_SCHEMA = "cast-event-cal.api.v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _events(payload: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError("public/events.json must be an object with an events array")
    rows = payload["events"]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("every event must be an object")
    if payload.get("count") != len(rows):
        raise ValueError("count does not match events length")
    return payload, rows


def build(source: Path, output_dir: Path) -> dict[str, Any]:
    payload, rows = _events(json.loads(source.read_text(encoding="utf-8")))
    ids = [str(row.get("id", "")).strip() for row in rows]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("event ids must be non-empty and unique")

    output_dir.mkdir(parents=True, exist_ok=True)
    api_events = output_dir / "events.json"
    api_csv = output_dir / "events.csv"
    facets_path = output_dir / "facets.json"
    manifest_path = output_dir / "manifest.json"

    _write_json(api_events, payload)

    fields = ["id", "title", "starts_at", "ends_at", "organizer", "location", "category", "status", "source", "url", "fetched_at"]
    with api_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in sorted(rows, key=lambda item: (str(item.get("starts_at") or ""), str(item.get("id") or ""))):
            writer.writerow({key: row.get(key) for key in fields})

    facet_fields = ("category", "status", "source", "event_mode")
    facets = {
        field: dict(sorted(Counter(str(row.get(field)) for row in rows if row.get(field) is not None).items()))
        for field in facet_fields
    }
    _write_json(facets_path, {"schema_version": API_SCHEMA, "event_count": len(rows), "facets": facets})

    files = {}
    for path in (api_events, api_csv, facets_path):
        files[path.name] = {"bytes": path.stat().st_size, "sha256": _sha256(path)}

    manifest = {
        "schema_version": API_SCHEMA,
        "source_schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "timezone": payload.get("timezone"),
        "event_count": len(rows),
        "source_sha256": _sha256(source),
        "cache": {"max_age_seconds": 900, "validation": "sha256"},
        "files": files,
    }
    _write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build versioned JSON/CSV/facet distributions for the public event feed")
    parser.add_argument("--source", type=Path, default=Path("public/events.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("public/api/v1"))
    args = parser.parse_args()
    manifest = build(args.source, args.output_dir)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
