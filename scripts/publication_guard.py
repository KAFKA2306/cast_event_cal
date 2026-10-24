from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
REASON_BASE_CHANGED = "base_changed_after_validation"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def validated_sha(value: object) -> str:
    if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
        raise ValueError("validated source SHA must be a full 40-character hex commit")
    return value


def record_base(path: Path) -> str:
    sha = validated_sha(git("rev-parse", "HEAD"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": 1, "validated_base_sha": sha}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return sha


def check_base(path: Path, snapshot_path: Path) -> str:
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("schema_version") != 1:
        raise ValueError("validated source manifest schema mismatch")
    source = validated_sha(record.get("validated_base_sha"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("source_revision") != source:
        raise RuntimeError("source_revision_mismatch: snapshot and validated base differ")
    checkout = validated_sha(git("rev-parse", "HEAD"))
    if checkout != source:
        raise RuntimeError(f"{REASON_BASE_CHANGED}: validated={source} checkout={checkout}")
    remote = git("ls-remote", "origin", "refs/heads/main")
    fields = remote.split()
    if len(fields) != 2 or fields[1] != "refs/heads/main":
        raise RuntimeError("unable to verify remote main revision")
    remote_sha = validated_sha(fields[0])
    if remote_sha != source:
        raise RuntimeError(f"{REASON_BASE_CHANGED}: validated={source} remote={remote_sha}")
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description="Bind published artifacts to validated main.")
    parser.add_argument("mode", choices=("record", "check"))
    parser.add_argument("--record", type=Path, default=Path("audit/validated-source.json"))
    parser.add_argument("--snapshot", type=Path, default=Path("public/snapshot.json"))
    args = parser.parse_args()
    try:
        sha = record_base(args.record) if args.mode == "record" else check_base(args.record, args.snapshot)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"publication guard failed: {exc}", file=sys.stderr)
        return 42
    print(json.dumps({"publication_guard": args.mode, "validated_base_sha": sha}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
