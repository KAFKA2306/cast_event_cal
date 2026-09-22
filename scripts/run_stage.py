from __future__ import annotations

import argparse
import glob
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.1"
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
                if label not in seen:
                    seen.add(label)
                    rows.append((label, path))
    return sorted(rows, key=lambda item: item[0])


def fingerprint_paths(root: Path, specs: Iterable[str]) -> dict[str, Any]:
    hasher = hashlib.sha256()
    files = _iter_files(root, specs)
    total_bytes = 0
    missing = 0
    for label, path in files:
        hasher.update(label.encode())
        hasher.update(b"\0")
        if path is None:
            missing += 1
            hasher.update(b"<missing>\0")
            continue
        data = path.read_bytes()
        total_bytes += len(data)
        hasher.update(str(len(data)).encode())
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
            for field in (
                "query_count",
                "queries_attempted",
                "network_request_count",
                "request_count",
                "requests",
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


def cache_key(input_sha: str, code_sha: str) -> str:
    return hashlib.sha256(f"{input_sha}:{code_sha}".encode()).hexdigest()


def restore_cache(root: Path, cache_dir: Path, outputs: list[str]) -> bool:
    manifest = cache_dir / "manifest.json"
    if not manifest.exists():
        return False
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("successful") is not True:
        return False
    for output in outputs:
        source = cache_dir / "outputs" / output
        if not source.exists():
            return False
    for output in outputs:
        source = cache_dir / "outputs" / output
        target = root / output
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    return True


def save_cache(root: Path, cache_dir: Path, outputs: list[str]) -> None:
    output_root = cache_dir / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    for output in outputs:
        source = root / output
        if not source.exists():
            continue
        target = output_root / output
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)
    (cache_dir / "manifest.json").write_text(
        json.dumps({"successful": True}), encoding="utf-8"
    )


def append_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--kind", choices=("setup", "network", "projection", "validation"), required=True
    )
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--code-input", action="append", default=[])
    parser.add_argument("--output", action="append", default=[])
    parser.add_argument("--measure-json", action="append", default=[])
    parser.add_argument("--cache-root")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a command is required after --")
    if args.cache_root and args.kind != "projection":
        parser.error("cache reuse is restricted to projection stages")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path.cwd()
    command = [str(part) for part in args.command]
    input_specs = list(args.input)
    code_specs = list(args.code_input)
    if (
        len(command) > 1
        and Path(command[0]).name.startswith("python")
        and command[1].endswith(".py")
        and Path(command[1]).exists()
    ):
        code_specs.append(command[1])
    inputs = fingerprint_paths(root, input_specs)
    code = fingerprint_paths(root, code_specs)
    output_before = fingerprint_paths(root, args.output)
    started_at = utc_now()
    started_counter = time.perf_counter()
    reused = False
    cache_dir = None
    if args.cache_root:
        cache_dir = (
            Path(args.cache_root)
            / args.name
            / cache_key(inputs["sha256"], code["sha256"])
        )
        reused = restore_cache(root, cache_dir, args.output)
    if reused:
        return_code = 0
    else:
        try:
            return_code = int(subprocess.run(command, check=False).returncode)
        except OSError as exc:
            print(f"stage command could not start: {exc}", file=sys.stderr)
            return_code = 127
        if return_code == 0 and cache_dir is not None:
            save_cache(root, cache_dir, args.output)
    output_after = fingerprint_paths(root, args.output)
    record = {
        "schema_version": SCHEMA_VERSION,
        "stage": args.name,
        "kind": args.kind,
        "status": "reused" if reused else ("executed" if return_code == 0 else "failed"),
        "reuse_reason": "matching_input_and_code_fingerprint" if reused else None,
        "return_code": return_code,
        "command": command,
        "started_at": isoformat(started_at),
        "finished_at": isoformat(utc_now()),
        "duration_seconds": round(max(0.0, time.perf_counter() - started_counter), 6),
        "input_fingerprint": inputs,
        "code_fingerprint": code,
        "output_before": output_before,
        "output_after": output_after,
        "output_changed": output_before["sha256"] != output_after["sha256"],
        "measurements_after": json_measurements(root, args.measure_json),
    }
    append_record(Path(args.report), record)
    print("STAGE_TELEMETRY " + json.dumps(record, ensure_ascii=False, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
