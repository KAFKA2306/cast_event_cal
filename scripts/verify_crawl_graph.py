from __future__ import annotations

import argparse
import json
from collections import Counter, deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from xml.etree import ElementTree as ET

try:
    from scripts.render_search_pages import BASE_URL
except ModuleNotFoundError:
    from render_search_pages import BASE_URL

SEARCH_PREFIXES = ("events/", "categories/", "series/")


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attributes = dict(attrs)
        if "download" in attributes:
            return
        href = attributes.get("href")
        if href:
            self.hrefs.append(href)


def canonicalize(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def url_to_file(public_root: Path, url: str, base_url: str) -> Path:
    if url == base_url:
        return public_root / "index.html"
    parsed = urlparse(url)
    base = urlparse(base_url)
    prefix = base.path.rstrip("/") + "/"
    if parsed.scheme != base.scheme or parsed.netloc != base.netloc or not parsed.path.startswith(prefix):
        raise ValueError(f"URL outside canonical host/path: {url}")
    relative = parsed.path[len(prefix):].rstrip("/")
    return public_root / relative / "index.html"


def sitemap_urls(public_root: Path) -> list[str]:
    sitemap = ET.parse(public_root / "sitemap.xml").getroot()
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [node.text for node in sitemap.findall("s:url/s:loc", ns)]
    if any(not isinstance(url, str) for url in urls):
        raise ValueError("sitemap contains an empty URL")
    return [canonicalize(str(url)) for url in urls]


def verify(public_root: Path, base_url: str = BASE_URL) -> dict[str, object]:
    base_url = base_url.rstrip("/") + "/"
    urls = sitemap_urls(public_root)
    if not urls or urls[0] != base_url:
        raise ValueError("sitemap must start with canonical homepage")
    if len(urls) != len(set(urls)):
        raise ValueError("sitemap contains duplicate URLs")

    canonical = set(urls)
    graph: dict[str, set[str]] = {url: set() for url in urls}
    broken_search_links: list[str] = []
    base = urlparse(base_url)
    search_root = base.path.rstrip("/") + "/"

    for page_url in urls:
        path = url_to_file(public_root, page_url, base_url)
        if not path.is_file():
            raise ValueError(f"sitemap HTML missing: {page_url}")
        parser = AnchorParser()
        parser.feed(path.read_text(encoding="utf-8"))
        for href in parser.hrefs:
            target = canonicalize(urljoin(page_url, href))
            if target in canonical:
                graph[page_url].add(target)
                continue
            parsed = urlparse(target)
            if parsed.scheme == base.scheme and parsed.netloc == base.netloc and parsed.path.startswith(search_root):
                relative = parsed.path[len(search_root):]
                if relative.startswith(SEARCH_PREFIXES):
                    broken_search_links.append(f"{page_url} -> {target}")

    if broken_search_links:
        preview = "; ".join(sorted(set(broken_search_links))[:10])
        raise ValueError(f"broken/non-canonical search links: {preview}")

    indegree: Counter[str] = Counter()
    for targets in graph.values():
        for target in targets:
            if target != base_url:
                indegree[target] += 1
    orphans = sorted(url for url in urls if url != base_url and indegree[url] == 0)
    if orphans:
        raise ValueError("orphan indexable pages: " + ", ".join(orphans[:10]))

    depth = {base_url: 0}
    queue: deque[str] = deque([base_url])
    while queue:
        source = queue.popleft()
        for target in sorted(graph[source]):
            if target not in depth:
                depth[target] = depth[source] + 1
                queue.append(target)
    unreachable = sorted(canonical - set(depth))
    if unreachable:
        raise ValueError("indexable pages unreachable from homepage: " + ", ".join(unreachable[:10]))

    event_urls = sorted(url for url in urls if "/events/" in url)
    event_without_inbound = [url for url in event_urls if indegree[url] == 0]
    if event_without_inbound:
        raise ValueError("event pages without inbound links: " + ", ".join(event_without_inbound[:10]))

    depth_histogram = Counter(depth.values())
    return {
        "page_count": len(urls),
        "event_page_count": len(event_urls),
        "edge_count": sum(len(targets) for targets in graph.values()),
        "orphan_count": 0,
        "broken_search_link_count": 0,
        "unreachable_count": 0,
        "event_pages_without_inbound": 0,
        "max_depth": max(depth.values(), default=0),
        "depth_histogram": {str(level): count for level, count in sorted(depth_histogram.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-root", type=Path, default=Path("public"))
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()
    print(json.dumps(verify(args.public_root, args.base_url), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
