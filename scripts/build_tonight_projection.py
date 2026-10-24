from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path("public/events.json")
DEFAULT_OUTPUT = Path("public/tonight/events.json")

# Delivery shape only. Canonical authority remains public/events.json.
FIELDS = (
    "id", "title", "canonical_name", "starts_at", "ends_at", "organizer",
    "category", "source", "primary_action_url", "official_links", "url",
    "participation_method", "event_mode", "confidence", "classification_reason",
    "description", "proof_links", "review_required",
)


def records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("events", "items", "data"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise ValueError("canonical event payload has no event array")


def project_event(event: dict[str, Any]) -> dict[str, Any]:
    return {key: event[key] for key in FIELDS if key in event}


def build(payload: Any) -> dict[str, Any]:
    events = records(payload)
    projected = [project_event(event) for event in events]
    result: dict[str, Any] = {"events": projected}
    if isinstance(payload, dict) and "generated_at" in payload:
        result["generated_at"] = payload["generated_at"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build lightweight Tonight projection from canonical public events")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="fail if output differs instead of writing")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    projected = build(payload)
    rendered = json.dumps(projected, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Tonight projection is stale or missing")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
