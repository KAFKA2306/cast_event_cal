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
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def run_git(root: Path, args: list[str]) -> bytes:
    completed = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    return completed.stdout


def changed_paths(root: Path) -> list[str]:
    tracked = run_git(root, ["diff", "--name-only", "-z", "HEAD"]).decode("utf-8").split("\0")
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard", "-z"]).decode("utf-8").split("\0")
    return sorted({path for path in tracked + untracked if path})


def git_metrics(root: Path) -> dict[str, Any]:
    paths = changed_paths(root)
    additions = 0
    deletions = 0
    numstat = run_git(root, ["diff", "--numstat", "HEAD"]).decode("utf-8")
    for line in numstat.splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        if parts[0].isdigit():
            additions += int(parts[0])
        if parts[1].isdigit():
            deletions += int(parts[1])
    working_tree_bytes = 0
    for relative in paths:
        path = root / relative
        if path.is_file():
            working_tree_bytes += path.stat().st_size
    patch_bytes = len(run_git(root, ["diff", "--binary", "HEAD"]))
    return {
        "changed_file_count": len(paths),
        "changed_files": paths,
        "changed_worktree_bytes": working_tree_bytes,
        "git_patch_bytes": patch_bytes,
        "line_additions": additions,
        "line_deletions": deletions,
    }


def network_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    stage_count = 0
    stages_with_request_count = 0
    stages_with_fetched_records = 0
    reported_requests = 0
    reported_fetched_records = 0
    for record in records:
        if record.get("kind") != "network":
            continue
        stage_count += 1
        measurements = record.get("measurements_after")
        if not isinstance(measurements, dict):
            continue
        request_values: list[int] = []
        fetched_values: list[int] = []
        for payload in measurements.values():
            if not isinstance(payload, dict):
                continue
            request_count = payload.get("reported_request_count")
            fetched_count = payload.get("reported_fetched_records")
            if isinstance(request_count, int):
                request_values.append(request_count)
            if isinstance(fetched_count, int):
                fetched_values.append(fetched_count)
        if request_values:
            stages_with_request_count += 1
            reported_requests += max(request_values)
        if fetched_values:
            stages_with_fetched_records += 1
            reported_fetched_records += max(fetched_values)
    return {
        "stage_count": stage_count,
        "stages_with_reported_request_count": stages_with_request_count,
        "reported_request_count": reported_requests,
        "stages_with_reported_fetched_records": stages_with_fetched_records,
        "reported_fetched_records": reported_fetched_records,
    }


def summarize(records: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    now = datetime.now(UTC)
    started = parse_instant(os.environ.get("UPDATE_RUN_STARTED_AT"))
    if started is None:
        starts = [parse_instant(str(record.get("started_at") or "")) for record in records]
        valid_starts = [item for item in starts if item is not None]
        started = min(valid_starts) if valid_starts else now

    status_counts: dict[str, int] = {}
    kind_seconds: dict[str, float] = {}
    for record in records:
        status = str(record.get("status") or "unknown")
        kind = str(record.get("kind") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        kind_seconds[kind] = round(kind_seconds.get(kind, 0.0) + float(record.get("duration_seconds") or 0.0), 6)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "run": {
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "github_sha": os.environ.get("GITHUB_SHA"),
            "measured_pipeline_wall_clock_seconds": round(max(0.0, (now - started).total_seconds()), 6),
            "manual_trigger": os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch",
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


def write_step_summary(summary: dict[str, Any]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    stages = summary["stages"]["records"]
    lines = [
        "### Update pipeline cost telemetry",
        "",
        f"Measured wall clock: **{summary['run']['measured_pipeline_wall_clock_seconds']:.2f}s**",
        f"Changed files: **{summary['git']['changed_file_count']}** / Git patch: **{summary['git']['git_patch_bytes']} bytes**",
        f"Reported network requests: **{summary['network']['reported_request_count']}** across **{summary['network']['stages_with_reported_request_count']}** stages",
        "",
        "| Stage | Kind | Status | Seconds | Output changed |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for record in stages:
        lines.append(
            f"| {record.get('stage', '')} | {record.get('kind', '')} | {record.get('status', '')} | "
            f"{float(record.get('duration_seconds') or 0.0):.3f} | {record.get('output_changed', False)} |"
        )
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate update stage telemetry and Git churn metrics.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    records = read_records(Path(args.report))
    summary = summarize(records, root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_step_summary(summary)
    print("UPDATE_RUN_TELEMETRY " + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
