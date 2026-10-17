from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cast_event_cal.public_origin import public_origin

OWN_URL = re.compile(r'''(?:rel=["']canonical["'][^>]*href|property=["']og:url["'][^>]*content)=["']([^"']+)["']''', re.I)
SITEMAP_LOC = re.compile(r"<loc>([^<]+)</loc>")


def _origin(url: str) -> str:
    parsed = urlsplit(url.strip())
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""


def audit(root: Path, expected: str) -> list[str]:
    failures: list[str] = []
    html_paths = [root / "index.html", root / "tonight" / "index.html"]
    html_paths += sorted((root / "events").glob("*/index.html"))
    html_paths += sorted((root / "categories").glob("*/index.html"))
    html_paths += sorted((root / "series").glob("*/index.html"))
    for path in html_paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for url in OWN_URL.findall(text):
            if _origin(url) != expected:
                failures.append(f"{path}: own URL uses {_origin(url) or 'invalid origin'}: {url}")
    sitemap = root / "sitemap.xml"
    if sitemap.is_file():
        for url in SITEMAP_LOC.findall(sitemap.read_text(encoding="utf-8")):
            if _origin(url) != expected:
                failures.append(f"{sitemap}: sitemap URL uses {_origin(url) or 'invalid origin'}: {url}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail when indexable public surfaces drift from the canonical origin")
    parser.add_argument("--root", type=Path, default=Path("public"))
    args = parser.parse_args()
    expected = public_origin()
    failures = audit(args.root, expected)
    if failures:
        print(f"canonical origin drift: expected {expected}", file=sys.stderr)
        for failure in failures[:50]:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"canonical origin OK: {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
