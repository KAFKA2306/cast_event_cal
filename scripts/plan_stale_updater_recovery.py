"""Decide whether a late calendar updater merits one bounded recovery dispatch.

This module never calls GitHub. The workflow owns the actual dispatch permission.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def plan_recovery(
    audit: dict[str, Any],
    runs: list[dict[str, Any]],
    *,
    checked_at: datetime,
    cooldown_minutes: int,
) -> dict[str, Any]:
    """Fail closed on unknown data, active runs, or recent manual dispatches."""
    if audit.get("state") != "late":
        return {"dispatch": False, "reason": "audit_not_late"}
    if not runs:
        return {"dispatch": False, "reason": "no_updater_runs"}

    for run in runs:
        if not isinstance(run, dict) or run.get("status") != "completed":
            return {"dispatch": False, "reason": "updater_active_or_unknown"}
        started = parse_time(run.get("created_at"))
        if started is None:
            return {"dispatch": False, "reason": "invalid_run_timestamp"}
        age_minutes = (checked_at - started).total_seconds() / 60
        if age_minutes < 0:
            return {"dispatch": False, "reason": "future_run_timestamp"}
        if run.get("event") == "workflow_dispatch" and age_minutes < cooldown_minutes:
            return {
                "dispatch": False,
                "reason": "manual_dispatch_cooldown",
                "last_dispatch_age_minutes": round(age_minutes, 1),
            }

    return {"dispatch": True, "reason": "late_without_active_or_recent_manual_run"}


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
