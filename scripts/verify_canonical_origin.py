"""Read-only audit of public canonical and sitemap origins.

Do not enforce as a publication gate until the intended host is reachable
and renderer URLs have been migrated together.
"""
from __future__ import annotations

import argparse
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cast_event_cal.public_origin import public_origin


class SearchMetadata(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key.lower(): value for key, value in attrs}
        if tag == "link" and "canonical" in (data.get("rel") or "").lower().split():
            self.urls.append(("canonical", data.get("href") or ""))
        elif tag == "meta" and (data.get("property") or "").lower() == "og:url":
            self.urls.append(("og:url", data.get("content") or ""))


def _origin(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
            return ""
        return f"{parts.scheme}://{parts.netloc}"
    except ValueError:
        return ""


def audit(root: Path, expected: str) -> list[str]:
    failures: list[str] = []
    html_paths = [root / "index.html", root / "tonight" / "index.html"]
    for folder in ("events", "categories", "series"):
        html_paths.extend(sorted((root / folder).glob("*/index.html")))
    if not (root / "index.html").is_file():
        failures.append(f"{root}: missing root index.html")
    for path in html_paths:
        if not path.is_file():
            continue
        parser = SearchMetadata()
        parser.feed(path.read_text(encoding="utf-8"))
        for kind, url in parser.urls:
            if _origin(url) != expected:
                failures.append(f"{path}: {kind} origin drift: {url!r} (expected {expected})")
        if not any(kind == "canonical" for kind, _ in parser.urls):
            failures.append(f"{path}: missing canonical")
    sitemap = root / "sitemap.xml"
    if sitemap.is_file():
        try:
            tree = ElementTree.parse(sitemap)
            locs = [node.text or "" for node in tree.iter() if node.tag.rsplit("}", 1)[-1] == "loc"]
            if not locs:
                failures.append(f"{sitemap}: no sitemap loc elements")
            for url in locs:
                if _origin(url) != expected:
                    failures.append(f"{sitemap}: sitemap origin drift: {url!r} (expected {expected})")
        except ElementTree.ParseError as exc:
            failures.append(f"{sitemap}: invalid sitemap XML: {exc}")
    else:
        failures.append(f"{sitemap}: missing sitemap.xml")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit public search origins without modifying publication")
    parser.add_argument("--root", type=Path, default=Path("public"))
    args = parser.parse_args()
    expected = public_origin()
    failures = audit(args.root, expected)
    for failure in failures[:50]:
        print(f"- {failure}", file=sys.stderr)
    if failures:
        print(f"canonical origin drift: {len(failures)} findings, expected {expected}", file=sys.stderr)
        return 1
    print(f"canonical origin OK: {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
