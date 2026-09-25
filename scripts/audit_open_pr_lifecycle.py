from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

SUPERSEDES_RE = re.compile(r"\bSupersedes\s+#(\d+)\b", re.IGNORECASE)
SUPERSEDED_BY_RE = re.compile(r"\bSuperseded\s+by\s+#(\d+)\b", re.IGNORECASE)
ISSUE_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|refs?)\s+#(\d+)\b", re.IGNORECASE)


def api_get(url: str, token: str | None) -> Any:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def referenced_issues(body: str) -> list[int]:
    return sorted({int(value) for value in ISSUE_RE.findall(body or "")})


def supersession(body: str) -> dict[str, list[int]]:
    return {
        "supersedes": sorted({int(value) for value in SUPERSEDES_RE.findall(body or "")}),
        "superseded_by": sorted({int(value) for value in SUPERSEDED_BY_RE.findall(body or "")}),
    }


def classify(*, behind: int, superseded_by: list[int], overlapping_newer_prs: list[int], head_age_days: int) -> str:
    if superseded_by or overlapping_newer_prs:
        return "superseded-candidate"
    if behind > 0:
        return "needs-rebase"
    if head_age_days >= 30:
        return "stale-candidate"
    return "active"


def audit(repo: str, token: str | None, now: datetime) -> dict[str, Any]:
    base_url = f"https://api.github.com/repos/{repo}"
    pulls = api_get(f"{base_url}/pulls?state=open&per_page=100", token)
    rows: list[dict[str, Any]] = []
    issue_owners: dict[int, list[tuple[datetime, int]]] = {}
    for pr in pulls:
        for issue in referenced_issues(pr.get("body") or ""):
            issue_owners.setdefault(issue, []).append((parse_time(pr["created_at"]), pr["number"]))

    for pr in pulls:
        number = pr["number"]
        head_sha = pr["head"]["sha"]
        compare = api_get(f"{base_url}/compare/{urllib.parse.quote(pr['base']['ref'], safe='')}...{head_sha}", token)
        runs = api_get(f"{base_url}/actions/runs?head_sha={head_sha}&per_page=100", token).get("workflow_runs", [])
        exact_runs = [run for run in runs if run.get("head_sha") == head_sha]
        exact_ci = sorted(exact_runs, key=lambda run: run.get("created_at") or "", reverse=True)
        issues = referenced_issues(pr.get("body") or "")
        newer: set[int] = set()
        for issue in issues:
            owners = issue_owners.get(issue, [])
            current_created = parse_time(pr["created_at"])
            newer.update(candidate for created, candidate in owners if created > current_created and candidate != number)
        relation = supersession(pr.get("body") or "")
        head_commit = api_get(f"{base_url}/commits/{head_sha}", token)
        head_time = parse_time(head_commit["commit"]["committer"]["date"])
        updated = parse_time(pr["updated_at"])
        head_age = max(0, (now - head_time).days)
        status = classify(
            behind=int(compare.get("behind_by") or 0),
            superseded_by=relation["superseded_by"],
            overlapping_newer_prs=sorted(newer),
            head_age_days=head_age,
        )
        rows.append({
            "number": number,
            "title": pr["title"],
            "head_sha": head_sha,
            "base_ref": pr["base"]["ref"],
            "head_age_days": head_age,
            "last_update_age_days": max(0, (now - updated).days),
            "commits_behind_base": int(compare.get("behind_by") or 0),
            "exact_head_ci": {
                "present": bool(exact_ci),
                "latest_status": exact_ci[0].get("status") if exact_ci else None,
                "latest_conclusion": exact_ci[0].get("conclusion") if exact_ci else None,
                "run_id": exact_ci[0].get("id") if exact_ci else None,
            },
            "issue_refs": issues,
            "supersession": relation,
            "overlapping_newer_prs": sorted(newer),
            "status": status,
        })
    return {"schema_version": 1, "generated_at": now.isoformat().replace("+00:00", "Z"), "repository": repo, "pull_requests": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not args.repo:
        parser.error("--repo or GITHUB_REPOSITORY is required")
    report = audit(args.repo, os.environ.get("GITHUB_TOKEN"), datetime.now(UTC))
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
