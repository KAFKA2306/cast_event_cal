"""Decide whether a failed or late calendar updater merits one bounded recovery dispatch.

This module never calls GitHub. The workflow owns the actual dispatch permission.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

MAX_DISPATCHES_24H = 2
RUN_HISTORY_PAGE_SIZE = 100


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except (TypeError, ValueError):
        return None


def plan_recovery(
    audit: dict[str, Any],
    runs: list[dict[str, Any]],
    *,
    checked_at: datetime,
    cooldown_minutes: int,
) -> dict[str, Any]:
    """Fail closed on unknown state, incomplete history, active runs, or retry budget."""
    state = audit.get("state")
    if state not in {"late", "failed"}:
        return {"dispatch": False, "reason": "audit_not_recoverable"}
    if not runs:
        return {"dispatch": False, "reason": "no_updater_runs"}

    parsed: list[tuple[dict[str, Any], datetime]] = []
    for run in runs:
        if not isinstance(run, dict) or run.get("status") != "completed":
            return {"dispatch": False, "reason": "updater_active_or_unknown"}
        started = parse_time(run.get("created_at"))
        if started is None:
            return {"dispatch": False, "reason": "invalid_run_timestamp"}
        age_minutes = (checked_at - started).total_seconds() / 60
        if age_minutes < 0:
            return {"dispatch": False, "reason": "future_run_timestamp"}
        parsed.append((run, started))

    oldest = min(started for _, started in parsed)
    if len(parsed) >= RUN_HISTORY_PAGE_SIZE and oldest >= checked_at - timedelta(days=1):
        return {"dispatch": False, "reason": "run_history_incomplete_for_daily_budget"}

    recent = [
        (run, started)
        for run, started in parsed
        if checked_at - started < timedelta(days=1)
    ]
    if any(
        run.get("event") == "workflow_dispatch"
        and (checked_at - started).total_seconds() / 60 < cooldown_minutes
        for run, started in recent
    ):
        return {"dispatch": False, "reason": "manual_dispatch_cooldown"}
    dispatches = sum(run.get("event") == "workflow_dispatch" for run, _ in recent)
    if dispatches >= MAX_DISPATCHES_24H:
        return {
            "dispatch": False,
            "reason": "daily_dispatch_budget_exhausted",
            "dispatches_last_24h": dispatches,
        }

    # Do not pile a manual dispatch on top of a recent scheduled attempt.
    if any(
        (checked_at - started).total_seconds() / 60 < cooldown_minutes
        for _, started in recent
    ):
        return {"dispatch": False, "reason": "recent_updater_attempt"}
    return {
        "dispatch": True,
        "reason": f"{state}_without_active_or_recent_run",
        "dispatches_last_24h": dispatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config/updater_liveness.json"))
    parser.add_argument("--output", type=Path, default=Path("updater-recovery-decision.json"))
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--checked-at")
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    config = json.loads(args.config.read_text(encoding="utf-8"))
    checked_at = parse_time(args.checked_at) if args.checked_at else datetime.now(UTC)
    if checked_at is None:
        raise SystemExit("invalid --checked-at")
    cooldown = int(config["late_after_minutes"])
    if cooldown <= 0:
        raise SystemExit("invalid late_after_minutes")
    result = plan_recovery(
        audit,
        payload.get("runs", []),
        checked_at=checked_at,
        cooldown_minutes=cooldown,
    )
    result["checked_at"] = checked_at.isoformat().replace("+00:00", "Z")
    result["cooldown_minutes"] = cooldown
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as out:
            out.write(f"dispatch={'true' if result['dispatch'] else 'false'}\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
