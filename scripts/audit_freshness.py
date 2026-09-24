from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HEALTH = ROOT / "public" / "health.json"
DEFAULT_SNAPSHOT = ROOT / "public" / "snapshot.json"
DEFAULT_REPORT = ROOT / "public" / "freshness-audit.json"

# Maximum acceptable age of the *published canonical snapshot*.
DEFAULT_MAX_SNAPSHOT_AGE_MINUTES = 180


def parse_instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def generated_at(document: dict[str, Any]) -> datetime | None:
    for key in ("generated_at", "created_at", "updated_at"):
        parsed = parse_instant(document.get(key))
        if parsed:
            return parsed
    return None


def audit(
    health: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    now: datetime,
    max_snapshot_age_minutes: int,
) -> dict[str, Any]:
    timestamps = [stamp for stamp in (generated_at(health), generated_at(snapshot)) if stamp]
    published_at = max(timestamps) if timestamps else None
    age_minutes = (
        max(0.0, (now - published_at).total_seconds() / 60.0)
        if published_at
        else None
    )
    reasons: list[str] = []
    if published_at is None:
        reasons.append("missing_publication_timestamp")
    elif age_minutes is not None and age_minutes > max_snapshot_age_minutes:
        reasons.append("stale_public_snapshot")

    # Freshness and collection health are separate contracts. A newly generated
    # snapshot may be degraded because an optional source is unavailable; that
    # must not prevent publishing a fresh last-known-good projection. Collection
    # health is validated separately before this audit.
    return {
        "schema_version": "1.0",
        "checked_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "ok" if not reasons else "stale",
        "published_at": (
            published_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            if published_at
            else None
        ),
        "snapshot_age_minutes": round(age_minutes, 3) if age_minutes is not None else None,
        "max_snapshot_age_minutes": max_snapshot_age_minutes,
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail closed when the public calendar snapshot is stale")
    parser.add_argument("--health", type=Path, default=DEFAULT_HEALTH)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-age-minutes", type=int, default=DEFAULT_MAX_SNAPSHOT_AGE_MINUTES)
    parser.add_argument("--now", help="fixed ISO-8601 instant for deterministic tests")
    args = parser.parse_args()

    now = parse_instant(args.now) if args.now else datetime.now(UTC)
    if now is None:
        raise ValueError("--now must be timezone-aware ISO-8601")
    report = audit(
        read_object(args.health),
        read_object(args.snapshot),
        now=now,
        max_snapshot_age_minutes=args.max_age_minutes,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Freshness audit: status={report['status']} "
        f"age_minutes={report['snapshot_age_minutes']} "
        f"limit={report['max_snapshot_age_minutes']}"
    )
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
