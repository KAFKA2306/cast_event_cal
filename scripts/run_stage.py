from __future__ import annotations

import argparse
import glob
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"
IGNORED_PATH_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "__pycache__",
    ".venv",
    "node_modules",
}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def is_ephemeral(path: Path) -> bool:
    return bool(IGNORED_PATH_PARTS.intersection(path.parts)) or path.suffix in IGNORED_SUFFIXES


def utc_now() -> datetime:
    return datetime.now(UTC)


def isoformat(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _iter_files(root: Path, specs: Iterable[str]) -> list[tuple[str, Path | None]]:
    rows: list[tuple[str, Path | None]] = []
    seen: set[str] = set()
    for raw_spec in specs:
        spec = str(raw_spec)
        matches = [Path(item) for item in glob.glob(spec, recursive=True)]
        if not matches:
            key = f"missing:{spec}"
            if key not in seen:
                seen.add(key)
                rows.append((key, None))
            continue
        for match in matches:
            if match.is_dir():
                candidates = sorted(
                    path
                    for path in match.rglob("*")
                    if path.is_file() and not is_ephemeral(path)
                )
            elif match.is_file() and not is_ephemeral(match):
                candidates = [match]
            else:
                continue
            for path in candidates:
                try:
                    label = path.resolve().relative_to(root.resolve()).as_posix()
                except ValueError:
                    label = path.resolve().as_posix()
                if label in seen:
                    continue
                seen.add(label)
                rows.append((label, path))
    return sorted(rows, key=lambda item: item[0])


def fingerprint_paths(root: Path, specs: Iterable[str]) -> dict[str, Any]:
    hasher = hashlib.sha256()
    files = _iter_files(root, specs)
    total_bytes = 0
    missing = 0
    for label, path in files:
        hasher.update(label.encode("utf-8"))
        hasher.update(b"\0")
        if path is None:
            missing += 1
            hasher.update(b"<missing>\0")
            continue
        data = path.read_bytes()
        total_bytes += len(data)
        hasher.update(str(len(data)).encode("ascii"))
        hasher.update(b"\0")
        hasher.update(data)
        hasher.update(b"\0")
    if not files:
        hasher.update(b"<empty>")
    return {
        "sha256": hasher.hexdigest(),
        "file_count": sum(path is not None for _, path in files),
        "missing_spec_count": missing,
        "bytes": total_bytes,
    }


def json_measurements(root: Path, paths: Iterable[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    count_fields = {
        "count", "event_count", "candidate_count", "accepted_count", "rejected_count",
        "query_count", "queries_attempted", "queries_succeeded", "queries_failed",
        "request_count", "network_request_count", "requests", "fetched_posts",
        "accepted_posts", "fetched_candidates", "accepted_candidates",
        "rejected_candidates", "retained_events", "raw_candidate_count",
        "unique_candidates_this_run", "duplicate_observations_removed",
        "deduplicated_against_existing", "history_candidate_count",
        "history_accepted_count", "history_rejected_count", "source_timestamp_count",
    }
    for raw_path in paths:
        path = root / raw_path
        key = Path(raw_path).as_posix()
        if not path.exists():
            result[key] = {"status": "missing"}
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            result[key] = {"status": "invalid", "error": str(exc)}
            continue
        metrics: dict[str, Any] = {"status": "ok"}
        if isinstance(payload, list):
            metrics["root_items"] = len(payload)
        elif isinstance(payload, dict):
            for field, value in payload.items():
                if isinstance(value, list):
                    metrics[f"{field}_items"] = len(value)
                elif isinstance(value, int) and not isinstance(value, bool) and field in count_fields:
                    metrics[field] = value
            for field in (
                "query_count", "queries_attempted", "network_request_count",
                "request_count", "requests",
            ):
                if isinstance(payload.get(field), int):
                    metrics["reported_request_count"] = payload[field]
                    break
            for field in ("fetched_posts", "fetched_candidates", "raw_candidate_count"):
                if isinstance(payload.get(field), int):
                    metrics["reported_fetched_records"] = payload[field]
                    break
        result[key] = metrics
    return result


def append_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one update stage and append machine-readable telemetry."
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--kind", choices=("setup", "network", "projection", "validation"), required=True
    )
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--output", action="append", default=[])
    parser.add_argument("--measure-json", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a command is required after --")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path.cwd()
    command = [str(part) for part in args.command]
    input_specs = list(args.input)
    if (
        len(command) > 1
        and Path(command[0]).name.startswith("python")
        and command[1].endswith(".py")
        and Path(command[1]).exists()
    ):
        input_specs.append(command[1])
    input_fingerprint = fingerprint_paths(root, input_specs)
    output_before = fingerprint_paths(root, args.output)
    measurements_before = json_measurements(root, args.measure_json)
    started_at = utc_now()
    started_counter = time.perf_counter()
    try:
        return_code = int(subprocess.run(command, check=False).returncode)
    except OSError as exc:
        print(f"stage command could not start: {exc}", file=sys.stderr)
        return_code = 127
    finished_at = utc_now()
    output_after = fingerprint_paths(root, args.output)
    record = {
        "schema_version": SCHEMA_VERSION,
        "stage": args.name,
        "kind": args.kind,
        "status": "executed" if return_code == 0 else "failed",
        "return_code": return_code,
        "command": command,
        "started_at": isoformat(started_at),
        "finished_at": isoformat(finished_at),
        "duration_seconds": round(max(0.0, time.perf_counter() - started_counter), 6),
        "input_fingerprint": input_fingerprint,
        "output_before": output_before,
        "output_after": output_after,
        "output_changed": output_before["sha256"] != output_after["sha256"],
        "measurements_before": measurements_before,
        "measurements_after": json_measurements(root, args.measure_json),
    }
    append_record(Path(args.report), record)
    print("STAGE_TELEMETRY " + json.dumps(record, ensure_ascii=False, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
