from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "public" / "index.html"
README = ROOT / "README.md"
FEED = ROOT / "public" / "calendar.ics"

CANONICAL_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"')
CALENDAR_RE = re.compile(
    r'<link\s+rel="alternate"\s+type="text/calendar"[^>]*href="([^"]+)"'
)
README_ICAL_RE = re.compile(r"^- iCalendar:\s+(https://\S+)$", re.MULTILINE)


def verify_calendar_subscription_contract(root: Path = ROOT) -> str:
    index = (root / "public" / "index.html").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    feed = root / "public" / "calendar.ics"

    canonical_match = CANONICAL_RE.search(index)
    if not canonical_match:
        raise AssertionError("public/index.html is missing the canonical origin")
    canonical_page = canonical_match.group(1)
    expected_feed = urljoin(canonical_page, "calendar.ics")

    alternate_match = CALENDAR_RE.search(index)
    if not alternate_match:
        raise AssertionError("public/index.html is missing text/calendar autodiscovery")
    discovered_feed = urljoin(canonical_page, alternate_match.group(1))
    if discovered_feed != expected_feed:
        raise AssertionError(
            f"calendar autodiscovery drift: {discovered_feed!r} != {expected_feed!r}"
        )

    readme_match = README_ICAL_RE.search(readme)
    if not readme_match:
        raise AssertionError("README.md is missing the iCalendar subscription URL")
    if readme_match.group(1) != expected_feed:
        raise AssertionError(
            f"README calendar URL drift: {readme_match.group(1)!r} != {expected_feed!r}"
        )

    if not feed.is_file() or feed.stat().st_size == 0:
        raise AssertionError("canonical public/calendar.ics is missing or empty")

    return expected_feed


def main() -> int:
    feed = verify_calendar_subscription_contract()
    print(f"calendar subscription contract OK: {feed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
