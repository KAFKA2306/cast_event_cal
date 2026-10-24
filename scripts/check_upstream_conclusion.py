#!/usr/bin/env python3
"""Fail closed when a workflow_run upstream did not succeed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PASS = {"success"}
FAIL = {
    "failure",
    "cancelled",
    "timed_out",
    "action_required",
    "stale",
    "neutral",
    "skipped",
}


def classify(conclusion: str) -> str:
    if conclusion in PASS:
        return "pass"
    if conclusion in FAIL:
        return "fail"
    return "fail"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conclusion", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    state = classify(args.conclusion)
    report = {
        "upstream_run_id": args.run_id,
        "upstream_head_sha": args.head_sha,
        "upstream_conclusion": args.conclusion,
        "state": state,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if state == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
