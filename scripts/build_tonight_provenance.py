#!/usr/bin/env python3
"""Build the single machine-readable publication identity for Tonight."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RELEASE = "kafka-signal-v1.0.0"


def build(commit: str, *, production: bool) -> dict[str, object]:
    verified = bool(SHA_RE.fullmatch(commit))
    if production and not verified:
        raise ValueError("production provenance requires a resolved 40-character git SHA")
    return {
        "schema_version": 1,
        "release": RELEASE,
        "commit": commit if verified else "UNVERIFIED",
        "verified": verified,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    payload = build(args.commit.strip().lower(), production=args.production)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
