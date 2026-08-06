#!/usr/bin/env python3
"""Validate checked-in public calendar artifacts before publication."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlparse


class ValidationError(ValueError):
    """Raised when a published artifact violates the delivery contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _load_json(path: Path) -> object:
    _require(path.is_file(), f"missing artifact: {path}")
    text = path.read_text(encoding="utf-8")
    _require(bool(text.strip()), f"empty artifact: {path}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc


def _valid_http_url(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _event_identity(row: dict[str, object]) -> str:
    for key in ("id", "source_id", "uid"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return f"{key}:{value.strip()}"
    raise ValidationError("event is missing id, source_id, and uid")


def validate_events(payload: object, *, minimum_count: int) -> list[dict[str, object]]:
    _require(isinstance(payload, dict), "events.json root must be an object")
    rows = payload.get("events")
    count = payload.get("count")
    _require(isinstance(rows, list), "events.json must contain an events array")
    _require(isinstance(count, int), "events.json must contain an integer count")
    _require(count == len(rows), f"events count mismatch: count={count}, rows={len(rows)}")
    _require(count >= minimum_count, f"event count below safety floor: {count} < {minimum_count}")

    identities: set[str] = set()
    for index, raw in enumerate(rows):
        _require(isinstance(raw, dict), f"event[{index}] must be an object")
        row = raw
        identity = _event_identity(row)
        _require(identity not in identities, f"duplicate event identity: {identity}")
        identities.add(identity)

        title = row.get("title") or row.get("name")
        _require(isinstance(title, str) and bool(title.strip()), f"{identity} has no title")

        source_url = row.get("source_url") or row.get("url") or row.get("primary_action_url")
        _require(_valid_http_url(source_url), f"{identity} has no valid source URL")

        start = row.get("start") or row.get("start_at") or row.get("start_time")
        _require(isinstance(start, str) and bool(start.strip()), f"{identity} has no start timestamp")

    return rows


def validate_ics(path: Path, *, expected_events: int) -> None:
    _require(path.is_file(), f"missing artifact: {path}")
    text = path.read_text(encoding="utf-8")
    _require(text.startswith("BEGIN:VCALENDAR"), "calendar.ics is not an iCalendar document")
    _require(text.rstrip().endswith("END:VCALENDAR"), "calendar.ics is truncated")
    event_count = text.count("BEGIN:VEVENT")
    _require(event_count == expected_events, f"ICS/JSON event count mismatch: {event_count} != {expected_events}")


def validate_public_api(public_dir: Path, *, minimum_count: int) -> None:
    events_payload = _load_json(public_dir / "events.json")
    rows = validate_events(events_payload, minimum_count=minimum_count)
    validate_ics(public_dir / "calendar.ics", expected_events=len(rows))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-dir", type=Path, default=Path("public"))
    parser.add_argument("--minimum-count", type=int, default=1)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        validate_public_api(args.public_dir, minimum_count=args.minimum_count)
    except ValidationError as exc:
        print(f"public API validation failed: {exc}")
        return 1
    print(f"public API validation passed: {args.public_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
