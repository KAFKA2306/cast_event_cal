#!/usr/bin/env python3
"""Build a read-only organizer identity audit from canonical event JSON."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse


def normalize_label(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip().casefold()


def _https_origin(value: object) -> str | None:
    try:
        parsed = urlparse(str(value or ""))
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    return f"https://{parsed.hostname.lower()}"


def strong_keys(event: dict) -> tuple[str, ...]:
    keys: set[str] = set()
    group = event.get("group_id") or event.get("vrchat_group_id")
    if group:
        keys.add(f"vrchat-group:{str(group).strip().casefold()}")
    for field in ("official_url", "organizer_url"):
        origin = _https_origin(event.get(field))
        if origin:
            keys.add(f"official-origin:{origin}")
    return tuple(sorted(keys))


def audit(events: list[dict]) -> dict:
    rows = []
    by_label: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        raw = str(event.get("organizer") or event.get("host") or "").strip()
        if not raw:
            continue
        row = {
            "event_id": str(event.get("id") or event.get("event_id") or ""),
            "raw_label": raw,
            "normalized_label": normalize_label(raw),
            "strong_keys": list(strong_keys(event)),
            "starts_at": event.get("starts_at") or event.get("start_at"),
            "series": event.get("series") or event.get("series_id"),
        }
        rows.append(row)
        by_label[row["normalized_label"]].append(row)

    candidates = []
    collisions = []
    for label in sorted(by_label):
        members = by_label[label]
        keysets = {tuple(member["strong_keys"]) for member in members}
        nonempty = {keys for keys in keysets if keys}
        if len(nonempty) == 1 and all(keys for keys in keysets):
            decision = "merged"
        elif len(nonempty) > 1:
            decision = "distinct"
        else:
            decision = "ambiguous"
        evidence = sorted({key for member in members for key in member["strong_keys"]})
        candidate = {
            "normalized_label": label,
            "display_names": sorted({m["raw_label"] for m in members}),
            "decision": decision,
            "evidence": evidence,
            "event_ids": sorted(m["event_id"] for m in members),
            "series": sorted({str(m["series"]) for m in members if m["series"]}),
        }
        candidates.append(candidate)
        if len(candidate["display_names"]) > 1 or decision != "merged":
            collisions.append(candidate)

    return {"schema_version": 1, "raw_label_count": len(rows), "candidate_count": len(candidates), "candidates": candidates, "collisions": collisions}


def _records(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("events", "items", "data"):
            if isinstance(payload.get(key), list):
                return [x for x in payload[key] if isinstance(x, dict)]
    raise ValueError("input must contain an event list")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(_records(json.loads(args.input.read_text(encoding="utf-8"))))
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
