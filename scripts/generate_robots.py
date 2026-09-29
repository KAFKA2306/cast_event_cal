from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

CANONICAL_PUBLIC_ORIGIN = "https://vrc-cast-event-calender.pages.dev"


def canonical_base_url(value: str) -> str:
    value = value.rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        msg = "canonical base URL must be an absolute HTTPS URL without credentials"
        raise ValueError(msg)
    return value


def render_robots(base_url: str) -> str:
    base = canonical_base_url(base_url)
    return f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"


def verify_sitemap(sitemap: Path, base_url: str) -> None:
    base = canonical_base_url(base_url)
    root = ET.parse(sitemap).getroot()
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [node.text or "" for node in root.findall("s:url/s:loc", ns)]
    if not urls:
        raise ValueError("sitemap contains no URLs")
    prefix = base + "/"
    if any(not url.startswith(prefix) for url in urls):
        raise ValueError("sitemap contains a URL outside the canonical base URL")


def write_robots(public_root: Path, base_url: str) -> Path:
    verify_sitemap(public_root / "sitemap.xml", base_url)
    target = public_root / "robots.txt"
    target.write_text(render_robots(base_url), encoding="utf-8", newline="\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-root", type=Path, default=Path("public"))
    parser.add_argument("--base-url", default=CANONICAL_PUBLIC_ORIGIN)
    args = parser.parse_args()
    target = write_robots(args.public_root, args.base_url)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
