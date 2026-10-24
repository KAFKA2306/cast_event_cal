from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CONTRACT_VERSION = 1
REQUIRED_WORKFLOW = "CI"


def build_record(*, commit_sha: str, run: dict[str, Any], jobs: list[dict[str, Any]], validated_at: str) -> dict[str, Any]:
    if run.get("head_sha") != commit_sha:
        raise ValueError("workflow run does not validate the requested commit SHA")
    required = []
    for job in jobs:
        name = str(job.get("name") or "").strip()
        conclusion = job.get("conclusion")
        if not name:
            continue
        required.append({"name": name, "conclusion": conclusion})
    if not required:
        result = "unknown"
    elif all(item["conclusion"] == "success" for item in required):
        result = "success"
    else:
        result = "failure"
    return {
        "schema_version": CONTRACT_VERSION,
        "commit_sha": commit_sha,
        "validated_at": validated_at,
        "workflow": REQUIRED_WORKFLOW,
        "run_id": run.get("id"),
        "run_attempt": run.get("run_attempt"),
        "required_checks": required,
        "result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--run-json", type=Path, required=True)
    parser.add_argument("--jobs-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validated-at")
    args = parser.parse_args()
    run = json.loads(args.run_json.read_text(encoding="utf-8"))
    jobs_payload = json.loads(args.jobs_json.read_text(encoding="utf-8"))
    jobs = jobs_payload.get("jobs", jobs_payload) if isinstance(jobs_payload, dict) else jobs_payload
    validated_at = args.validated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    record = build_record(commit_sha=args.commit_sha, run=run, jobs=jobs, validated_at=validated_at)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if record["result"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
