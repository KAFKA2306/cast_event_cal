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


def main() -> int:
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    url = f"{api}/repos/{repository}/actions/workflows/{quote(WORKFLOW)}/runs?branch=main&status=success&per_page=5"
    request = Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cast-event-cal-liveness-watch",
    })
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise ValueError("GitHub Actions API response lacks workflow_runs")
    healthy, message = evaluate(runs, datetime.now(UTC))
    print(message, file=sys.stdout if healthy else sys.stderr)
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
