from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path("public/events.json")
DEFAULT_OUTPUT = Path("public/tonight/events.json")

# Delivery shape only. Canonical authority remains public/events.json.
FIELDS = (
    "id",
    "event_id",
    "slug",
    "title",
    "name",
    "event_name",
    "canonical_name",
    "starts_at",
    "start_at",
    "start_time",
    "start",
    "datetime",
    "event_start",
    "date",
    "ends_at",
    "end_at",
    "end_time",
    "end",
    "event_end",
    "organizer",
    "host",
    "group_name",
    "author",
    "account_name",
    "category",
    "primary_category",
    "genre",
    "classification",
    "source",
    "source_type",
    "provider",
    "source_name",
    "primary_action_url",
    "official_links",
    "url",
    "official_url",
    "source_url",
    "announcement_url",
    "tweet_url",
    "join_url",
    "participation_url",
    "group_url",
    "request_url",
    "participation_method",
    "join_method",
    "how_to_join",
    "participation",
    "event_mode",
    "mode",
    "instance_type",
    "format",
    "confidence",
    "classification_confidence",
    "date_confidence",
    "classification_reason",
    "reason",
    "evidence_text",
    "category_reason",
    "description",
    "summary",
    "body",
    "proof_links",
    "evidence_links",
    "assets",
    "sources",
    "review_required",
)


def records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return _validated_rows(payload)
    if isinstance(payload, dict):
        for key in ("events", "items", "data"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return _validated_rows(rows)
    raise ValueError("canonical event payload has no event array")


def _validated_rows(rows: list[Any]) -> list[dict[str, Any]]:
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("canonical event array contains a non-object record")
    return rows


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
