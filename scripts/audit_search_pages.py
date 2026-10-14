from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

CANONICAL_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"', re.I)
ROBOTS_RE = re.compile(r'<meta\s+name="robots"\s+content="([^"]+)"', re.I)


def audit(public_root: Path) -> dict[str, object]:
    sitemap = public_root / "sitemap.xml"
    if not sitemap.exists():
        return {"status": "error", "reasons": ["missing_sitemap"], "checked_pages": 0}
    root = ElementTree.fromstring(sitemap.read_text(encoding="utf-8"))
    urls = [node.text or "" for node in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    reasons: list[str] = []
    checked = 0
    seen: set[str] = set()
    for url in urls:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc:
            reasons.append(f"invalid_sitemap_url:{url}")
            continue
        if url in seen:
            reasons.append(f"duplicate_sitemap_url:{url}")
        seen.add(url)
        if "/events/" not in parsed.path:
            continue
        event_id = parsed.path.rstrip("/").split("/")[-1]
        page = public_root / "events" / event_id / "index.html"
        if not page.exists():
            reasons.append(f"missing_event_page:{event_id}")
            continue
        checked += 1
        text = page.read_text(encoding="utf-8")
        canonical = CANONICAL_RE.search(text)
        if canonical is None:
            reasons.append(f"missing_canonical:{event_id}")
        elif canonical.group(1) != url:
            reasons.append(f"canonical_mismatch:{event_id}")
        robots = ROBOTS_RE.search(text)
        if robots is None or "index" not in robots.group(1).lower():
            reasons.append(f"not_indexable:{event_id}")
        if '<meta name="description"' not in text:
            reasons.append(f"missing_description:{event_id}")
        if '<meta property="og:title"' not in text or '<meta property="og:url"' not in text:
            reasons.append(f"missing_open_graph:{event_id}")
    return {"schema_version": "1.0", "status": "ok" if not reasons else "error", "sitemap_url_count": len(urls), "checked_pages": checked, "reasons": reasons}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-root", type=Path, default=Path("public"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = audit(args.public_root)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
