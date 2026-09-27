from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_INPUTS = (Path("data/recurring_events.json"), Path("data/manual_events.json"))
DEFAULT_DUE_DAYS = 90


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def official_url(record: dict[str, Any]) -> str | None:
    for key in ("official_url", "group_url", "url", "source_url"):
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            parsed = urlparse(value)
        except ValueError:
            continue
        if parsed.scheme == "https" and parsed.netloc:
            return value
    return None


def evidence_present(record: dict[str, Any]) -> bool:
    return any(
        record.get(key)
        for key in (
            "provenance",
            "evidence",
            "evidence_url",
            "source_url",
            "source_created_at",
            "last_verified_at",
        )
    )


def stable_identity(record: dict[str, Any]) -> str:
    for key in ("series_id", "source_id", "id"):
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value)
    raise ValueError("manual record has no stable identity (series_id/source_id/id)")


def classify(record: dict[str, Any], *, now: datetime, due_days: int) -> dict[str, Any]:
    identity = stable_identity(record)
    url = official_url(record)
    raw_verified = record.get("last_verified_at")
    verified = parse_time(raw_verified)
    if raw_verified and verified is None:
        state, reason = "unknown", "invalid_last_verified_at"
    elif verified is None:
        state, reason = "unknown", "last_verified_at_missing"
    else:
        age_days = max(0, (now - verified).total_seconds() / 86400)
        if age_days > due_days:
            state, reason = "overdue", "verification_older_than_threshold"
        elif age_days >= due_days * 0.8:
            state, reason = "due", "verification_near_threshold"
        else:
            state, reason = "verified", "verification_within_threshold"
    return {
        "identity": identity,
        "title": record.get("title") or record.get("canonical_name"),
        "official_url": url,
        "machine_verifiable_official_url": bool(url),
        "evidence_present": evidence_present(record),
        "last_verified_at": verified.isoformat().replace("+00:00", "Z") if verified else None,
        "verification_state": state,
        "reason": reason,
    }


def audit(records: list[dict[str, Any]], *, now: datetime, due_days: int = DEFAULT_DUE_DAYS) -> dict[str, Any]:
    rows = sorted((classify(row, now=now, due_days=due_days) for row in records), key=lambda row: row["identity"])
    counts = {state: sum(row["verification_state"] == state for row in rows) for state in ("verified", "due", "overdue", "unknown")}
    queue = [row["identity"] for row in rows if row["verification_state"] in {"due", "overdue", "unknown"}]
    return {
        "schema_version": "1.0",
        "as_of": now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "due_days": due_days,
        "record_count": len(rows),
        "state_counts": counts,
        "human_queue_count": len(queue),
        "human_queue": queue,
        "records": rows,
    }


def load(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{path} must contain a JSON array")
        records.extend(row for row in payload if isinstance(row, dict))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit manual/recurring event renewal evidence without changing canonical facts")
    parser.add_argument("--input", action="append", type=Path, dest="inputs")
    parser.add_argument("--now", required=True, help="Fixed RFC3339 instant; required for deterministic output")
    parser.add_argument("--due-days", type=int, default=DEFAULT_DUE_DAYS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    now = parse_time(args.now)
    if now is None:
        raise SystemExit("--now must be a valid RFC3339 instant")
    if args.due_days <= 0:
        raise SystemExit("--due-days must be positive")
    result = audit(load(args.inputs or list(DEFAULT_INPUTS)), now=now, due_days=args.due_days)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
