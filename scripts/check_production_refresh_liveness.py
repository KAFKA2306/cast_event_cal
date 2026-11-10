"""Independently verify that the production calendar workflow has completed recently."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from urllib.request import Request, urlopen


WORKFLOW = "update-calendar-v2.yml"
MAX_AGE = timedelta(hours=3)
RECOVERY_COOLDOWN = timedelta(minutes=90)
MAX_RECOVERIES_PER_DAY = 2


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp is missing timezone")
    return parsed.astimezone(UTC)


def evaluate(runs: list[dict], now: datetime, max_age: timedelta = MAX_AGE) -> tuple[bool, str]:
    if now.tzinfo is None:
        raise ValueError("now must have timezone")
    completed: list[tuple[datetime, str]] = []
    for run in runs:
        if run.get("head_branch") != "main" or run.get("conclusion") != "success":
            continue
        raw = run.get("updated_at") or run.get("created_at")
        if not isinstance(raw, str):
            continue
        try:
            when = parse_utc(raw)
        except ValueError:
            continue
        completed.append((when, str(run.get("html_url") or "")))
    if not completed:
        return False, "no successful main-branch production refresh run found"
    when, url = max(completed)
    age = now.astimezone(UTC) - when
    if age < timedelta(0):
        return False, f"latest successful refresh timestamp is in the future: {when.isoformat()}"
    if age > max_age:
        return False, f"latest successful refresh is {int(age.total_seconds() // 60)} minutes old (limit {int(max_age.total_seconds() // 60)}): {url}"
    return True, f"latest successful refresh is {int(age.total_seconds() // 60)} minutes old: {url}"


def recovery_decision(runs: list[dict], now: datetime) -> tuple[bool, str]:
    """Bound recovery attempts even when scheduling or source collection is broken."""
    recent_dispatches = 0
    for run in runs:
        if run.get("head_branch") != "main":
            continue
        raw = run.get("created_at")
        if not isinstance(raw, str):
            continue
        try:
            created = parse_utc(raw)
        except ValueError:
            continue
        age = now.astimezone(UTC) - created
        if age < timedelta(0):
            continue
        if age <= RECOVERY_COOLDOWN:
            return False, "a production refresh was already requested recently"
        if age <= timedelta(days=1) and run.get("event") == "workflow_dispatch":
            recent_dispatches += 1
        if age <= timedelta(hours=3) and run.get("status") in {
            "queued", "in_progress", "waiting", "pending", "requested"
        }:
            return False, "a production refresh is still running"
    if recent_dispatches >= MAX_RECOVERIES_PER_DAY:
        return False, "daily dispatch budget exhausted; preserve failure signal"
    return True, "no recent attempt or active run; one bounded recovery is allowed"


def main() -> int:
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    endpoint = f"{api}/repos/{repository}/actions/workflows/{quote(WORKFLOW)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cast-event-cal-liveness-watch",
    }
    request = Request(f"{endpoint}/runs?branch=main&per_page=50", headers=headers)
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise ValueError("GitHub Actions API response lacks workflow_runs")
    now = datetime.now(UTC)
    healthy, message = evaluate(runs, now)
    print(message, file=sys.stdout if healthy else sys.stderr)
    if healthy:
        return 0
    allowed, reason = recovery_decision(runs, now)
    if allowed:
        dispatch = Request(
            f"{endpoint}/dispatches",
            data=json.dumps({"ref": "main", "inputs": {"recovery_attempt": "1"}}).encode("utf-8"),
            headers={**headers, "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(dispatch, timeout=20) as response:
            if response.status not in {200, 202, 204}:
                raise RuntimeError(f"unexpected recovery dispatch status: {response.status}")
        print("dispatched one bounded production refresh recovery", file=sys.stderr)
    else:
        print(f"recovery suppressed: {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
