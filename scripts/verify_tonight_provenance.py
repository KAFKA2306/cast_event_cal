#!/usr/bin/env python3
"""Fail closed when Tonight publication identity drifts."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
LITERAL_RE = re.compile(r"[0-9a-f]{40}")


def verify(root: Path, *, production: bool) -> None:
    provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    commit = provenance.get("commit", "")
    verified = provenance.get("verified") is True and bool(SHA_RE.fullmatch(commit))
    if production and not verified:
        raise ValueError("production candidate has unresolved provenance")
    for name in ("index.html", "kafka-signal.js"):
        text = (root / name).read_text(encoding="utf-8")
        if LITERAL_RE.search(text):
            raise ValueError(f"hand-maintained commit literal remains in {name}")
    html = (root / "index.html").read_text(encoding="utf-8")
    if 'rel="publication-provenance" href="./provenance.json"' not in html:
        raise ValueError("Tonight HTML does not expose machine-readable provenance")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("public/tonight"))
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    verify(args.root, production=args.production)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
