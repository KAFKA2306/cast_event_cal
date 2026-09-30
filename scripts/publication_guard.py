from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REASON_BASE_CHANGED = "base_changed_after_validation"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def record_validated_base(output: Path) -> str:
    sha = git("rev-parse", "HEAD")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"validated_base_sha": sha}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return sha


def load_validated_base(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sha = str(payload.get("validated_base_sha") or "").strip()
    if not sha:
        raise ValueError("validated_base_sha is missing")
    return sha


def assert_same_base(validated_base_sha: str, remote_base_sha: str) -> None:
    if remote_base_sha != validated_base_sha:
        raise RuntimeError(
            f"{REASON_BASE_CHANGED}: validated={validated_base_sha} remote={remote_base_sha}"
        )


def check_remote_base(record: Path, remote_ref: str) -> str:
    validated = load_validated_base(record)
    git("fetch", "--no-tags", "origin", "main")
    remote = git("rev-parse", remote_ref)
    assert_same_base(validated, remote)
    return validated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guard publication against post-validation base changes.")
    parser.add_argument("mode", choices=("record", "check"))
    parser.add_argument("--record", type=Path, default=Path("/tmp/validated-base.json"))
    parser.add_argument("--remote-ref", default="refs/remotes/origin/main")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "record":
        sha = record_validated_base(args.record)
        print(json.dumps({"validated_base_sha": sha}, sort_keys=True))
        return 0

    try:
        sha = check_remote_base(args.record, args.remote_ref)
    except RuntimeError as exc:
        print(str(exc))
        return 42
    print(json.dumps({"publication_guard": "ok", "validated_base_sha": sha}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
