from __future__ import annotations

import argparse
import html.parser
import json
from pathlib import Path
from urllib.parse import urlsplit

from scripts.public_link_policy import safe_public_url

URL_FIELDS = {
    "primary_action_url", "url", "official_url", "source_url", "announcement_url",
    "join_url", "participation_url", "group_url", "request_url", "tweet_url",
}


class LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        values = dict(attrs)
        href = values.get("href")
        if href:
            self.hrefs.append(href)


def is_external(value: str) -> bool:
    parsed = urlsplit(value)
    return bool(parsed.scheme or parsed.netloc)


def audit_html(path: Path) -> list[str]:
    parser = LinkParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return [f"{path}:{href}" for href in parser.hrefs if is_external(href) and safe_public_url(href) is None]


def walk_urls(value: object, path: str = "$") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in URL_FIELDS and isinstance(child, str):
                rows.append((child_path, child))
            elif key in {"official_links", "proof_links", "evidence_links", "assets", "sources"}:
                rows.extend(walk_urls(child, child_path))
            elif isinstance(child, (dict, list)):
                rows.extend(walk_urls(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(walk_urls(child, f"{path}[{index}]") )
    return rows


def audit_json(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [f"{path}:{where}:{url}" for where, url in walk_urls(payload) if url and safe_public_url(url) is None]


def audit_public(root: Path) -> list[str]:
    failures: list[str] = []
    for path in root.rglob("*.html"):
        failures.extend(audit_html(path))
    events = root / "events.json"
    if events.exists():
        failures.extend(audit_json(events))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default="public")
    args = parser.parse_args()
    failures = audit_public(Path(args.root))
    if failures:
        print("unsafe public outbound links detected:")
        print("\n".join(failures))
        return 1
    print("public outbound link audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
