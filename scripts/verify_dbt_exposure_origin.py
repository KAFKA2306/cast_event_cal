from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cast_event_cal.public_origin import ENV_NAME, public_origin

URL_LINE = re.compile(r"^\s*url:\s*[\"']?(.+?)[\"']?\s*$")
ENV_TOKEN = "{{ env_var('" + ENV_NAME + "') }}"


def audit(path: Path, expected: str) -> list[str]:
    failures: list[str] = []
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = URL_LINE.match(line)
        if match:
            urls.append(match.group(1))

    if not urls:
        return [f"{path}: no exposure URLs found"]

    for url in urls:
        if not url.startswith(ENV_TOKEN + "/"):
            failures.append(f"{path}: exposure URL bypasses canonical origin authority: {url}")
            continue
        resolved = expected + url[len(ENV_TOKEN) :]
        if not resolved.startswith(expected + "/"):
            failures.append(f"{path}: exposure URL resolves outside canonical origin: {resolved}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail when dbt exposure URLs bypass canonical public-origin authority")
    parser.add_argument("--path", type=Path, default=Path("analytics/dbt/models/exposures.yml"))
    args = parser.parse_args()
    expected = public_origin()
    failures = audit(args.path, expected)
    if failures:
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"dbt exposure origins OK: {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
