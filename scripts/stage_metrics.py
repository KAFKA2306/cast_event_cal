#!/usr/bin/env python3
"""Run a production stage and append safe machine-readable timing evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def fingerprint(paths: list[str]) -> str | None:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(p for p in path.rglob("*") if p.is_file())
    if not files:
        return None
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda p: p.as_posix()):
        digest.update(path.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def total_bytes(paths: list[str]) -> int | None:
    files: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            files.add(path)
        elif path.is_dir():
            files.update(p for p in path.rglob("*") if p.is_file())
    return sum(p.stat().st_size for p in files) if files else None


def append_report(path: Path, record: dict[str, object]) -> None:
    payload: dict[str, object] = {"schema_version": 1, "stages": []}
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    stages = payload.setdefault("stages", [])
    if not isinstance(stages, list):
        raise ValueError("stage metrics report has invalid stages field")
    stages.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="artifacts/stage-metrics.json")
    parser.add_argument("--name", required=True)
    parser.add_argument("--class", dest="stage_class", required=True, choices=("network", "projection", "validation", "publication"))
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--output", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")

    started = datetime.now(timezone.utc)
    before_bytes = total_bytes(args.output)
    input_hash = fingerprint(args.input)
    start_clock = time.monotonic()
    completed = subprocess.run(command, check=False)
    duration = time.monotonic() - start_clock
    finished = datetime.now(timezone.utc)
    after_bytes = total_bytes(args.output)

    record: dict[str, object] = {
        "name": args.name,
        "class": args.stage_class,
        "state": "executed" if completed.returncode == 0 else "failed",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round(duration, 6),
        "exit_code": completed.returncode,
        "input_fingerprint": input_hash,
        "output_fingerprint": fingerprint(args.output),
        "changed_bytes": None if before_bytes is None or after_bytes is None else after_bytes - before_bytes,
    }
    append_report(Path(args.report), record)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
