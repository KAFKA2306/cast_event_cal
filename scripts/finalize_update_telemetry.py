from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"


def parse_instant(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def run_git(root: Path, args: list[str]) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True
    ).stdout


def git_metrics(root: Path) -> dict[str, Any]:
    tracked = run_git(root, ["diff", "--name-only", "-z", "HEAD"]).decode().split("\0")
    untracked = run_git(
        root, ["ls-files", "--others", "--exclude-standard", "-z"]
    ).decode().split("\0")
    paths = sorted({path for path in tracked + untracked if path})
    additions = deletions = 0
    for line in run_git(root, ["diff", "--numstat", "HEAD"]).decode().splitlines():
        parts = line.split("\t", 2)
        if len(parts) >= 2:
            if parts[0].isdigit():
                additions += int(parts[0])
            if parts[1].isdigit():
                deletions += int(parts[1])
    return {
        "changed_file_count": len(paths),
        "changed_files": paths,
        "changed_worktree_bytes": sum(
            (root / path).stat().st_size for path in paths if (root / path).is_file()
        ),
        "git_patch_bytes": len(run_git(root, ["diff", "--binary", "HEAD"])),
        "line_additions": additions,
        "line_deletions": deletions,
    }


def network_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    stage_count = with_requests = with_fetched = requests = fetched = 0
    for record in records:
        if record.get("kind") != "network":
            continue
        stage_count += 1
        request_values = []
        fetched_values = []
        for payload in (record.get("measurements_after") or {}).values():
            if not isinstance(payload, dict):
                continue
            if isinstance(payload.get("reported_request_count"), int):
                request_values.append(payload["reported_request_count"])
            if isinstance(payload.get("reported_fetched_records"), int):
                fetched_values.append(payload["reported_fetched_records"])
        if request_values:
            with_requests += 1
            requests += max(request_values)
        if fetched_values:
            with_fetched += 1
            fetched += max(fetched_values)
    return {
        "stage_count": stage_count,
        "stages_with_reported_request_count": with_requests,
        "reported_request_count": requests,
        "stages_with_reported_fetched_records": with_fetched,
        "reported_fetched_records": fetched,
    }


def summarize(records: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    now = datetime.now(UTC)
    started = parse_instant(os.environ.get("UPDATE_RUN_STARTED_AT"))
    if started is None:
        starts = [parse_instant(str(record.get("started_at") or "")) for record in records]
        valid = [instant for instant in starts if instant is not None]
        started = min(valid) if valid else now
    status_counts: dict[str, int] = {}
    kind_seconds: dict[str, float] = {}
    for record in records:
        status = str(record.get("status") or "unknown")
        kind = str(record.get("kind") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        kind_seconds[kind] = round(
            kind_seconds.get(kind, 0.0) + float(record.get("duration_seconds") or 0.0),
            6,
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "run": {
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_sha": os.environ.get("GITHUB_SHA"),
            "measured_pipeline_wall_clock_seconds": round(
                max(0.0, (now - started).total_seconds()), 6
            ),
        },
        "stages": {
            "count": len(records),
            "status_counts": status_counts,
            "kind_seconds": kind_seconds,
            "records": records,
        },
        "network": network_metrics(records),
        "git": git_metrics(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    summary = summarize(read_records(Path(args.report)), Path.cwd())
    Path(args.output).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "UPDATE_RUN_TELEMETRY "
        + json.dumps(summary, ensure_ascii=False, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
