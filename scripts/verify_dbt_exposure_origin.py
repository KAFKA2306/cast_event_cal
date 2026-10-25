"""Verify dbt exposure URLs follow the configured canonical-origin authority."""
from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cast_event_cal.public_origin import DEFAULT_PUBLIC_ORIGIN, ENV_NAME

EXPECTED_TOKEN = (
    "{{ env_var('" + ENV_NAME + "', '" + DEFAULT_PUBLIC_ORIGIN + "') }}"
)
URL_LINE = re.compile(r"^\s*url:\s*(.+?)\s*$")


def audit(path: Path) -> list[str]:
    failures: list[str] = []
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = URL_LINE.match(line)
        if match:
            url = match.group(1).strip().strip('"')
            urls.append(url)
            if not url.startswith(EXPECTED_TOKEN + "/"):
                failures.append(
                    f"{path}: exposure URL bypasses canonical origin: {url}"
                )
    if not urls:
        failures.append(f"{path}: no exposure URLs found")
    return failures


def main() -> int:
    path = Path("analytics/dbt/models/exposures.yml")
    failures = audit(path)
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print(f"dbt exposure origin OK: {DEFAULT_PUBLIC_ORIGIN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
