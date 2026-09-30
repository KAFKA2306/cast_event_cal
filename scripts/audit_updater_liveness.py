from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def instant(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def evaluate(payload: dict[str, Any], *, checked_at: datetime, late_after_minutes: int) -> dict[str, Any]:
    runs = [r for r in payload.get("runs", []) if isinstance(r, dict)]
    if not runs:
        return _result(checked_at, None, None, None, "unknown")
    runs.sort(key=lambda r: instant(r.get("created_at")) or datetime.min.replace(tzinfo=UTC), reverse=True)
    latest = runs[0]
    latest_at = instant(latest.get("created_at"))
    successes = [r for r in runs if r.get("conclusion") == "success" and instant(r.get("created_at"))]
    success_at = max((instant(r.get("created_at")) for r in successes), default=None)
    age = None if success_at is None else round((checked_at - success_at).total_seconds() / 60, 1)
    jobs = payload.get("jobs_by_run", {}).get(str(latest.get("id")))
    latest_failed = latest.get("status") == "completed" and latest.get("conclusion") not in {"success", "skipped"}
    zero_jobs = latest.get("status") == "completed" and isinstance(jobs, list) and not jobs
    if latest_failed or zero_jobs:
        state = "failed"
    elif success_at is None or age is None or age > late_after_minutes:
        state = "late"
    else:
        state = "healthy"
    return _result(checked_at, latest_at, success_at, age, state)


def _result(checked_at: datetime, latest_at: datetime | None, success_at: datetime | None, age: float | None, state: str) -> dict[str, Any]:
    def fmt(value: datetime | None) -> str | None:
        return value.isoformat().replace("+00:00", "Z") if value else None

    return {"checked_at": fmt(checked_at), "latest_run_at": fmt(latest_at), "latest_success_at": fmt(success_at), "age_minutes": age, "state": state}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--config", default=Path("config/updater_liveness.json"), type=Path)
    parser.add_argument("--output", default=Path("updater-liveness.json"), type=Path)
    parser.add_argument("--checked-at")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    checked_at = instant(args.checked_at) if args.checked_at else datetime.now(UTC)
    if checked_at is None:
        raise SystemExit("invalid --checked-at")
    result = evaluate(payload, checked_at=checked_at, late_after_minutes=int(config["late_after_minutes"]))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["state"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
