from __future__ import annotations

import argparse
import html
import json
import re
from collections import defaultdict
from pathlib import Path

try:
    from scripts.render_search_pages import parse_time
except ModuleNotFoundError:
    from render_search_pages import parse_time

ROOT_HUB_START = "<!-- crawl-hubs:start -->"
ROOT_HUB_END = "<!-- crawl-hubs:end -->"
ROOT_EVENTS_START = "<!-- crawl-all-events:start -->"
ROOT_EVENTS_END = "<!-- crawl-all-events:end -->"
EVENT_LINKS_START = "<!-- event-crawl-links:start -->"
EVENT_LINKS_END = "<!-- event-crawl-links:end -->"
CATEGORY_LINK_START = "<!-- category-related:start -->"
CATEGORY_LINK_END = "<!-- category-related:end -->"


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def replace_block(text: str, start: str, end: str, block: str, marker: str) -> str:
    text = re.sub(re.escape(start) + r".*?" + re.escape(end), "", text, flags=re.S)
    if marker not in text:
        raise ValueError(f"HTML marker missing: {marker}")
    return text.replace(marker, f"{start}{block}{end}{marker}", 1)


def page_label(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"<h1>(.*?)</h1>", text, flags=re.S)
    if not match:
        return path.parent.name
    return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip() or path.parent.name


def render(public_root: Path) -> dict[str, int]:
    payload = json.loads((public_root / "events.json").read_text(encoding="utf-8"))
    rows = payload.get("events")
    if not isinstance(rows, list):
        raise ValueError("events.json events must be a list")
    by_id = {str(row.get("id")): row for row in rows if isinstance(row, dict) and row.get("id")}

    event_paths = sorted((public_root / "events").glob("*/index.html"))
    event_ids = {path.parent.name for path in event_paths}
    category_paths = sorted((public_root / "categories").glob("*/index.html"))
    series_paths = sorted((public_root / "series").glob("*/index.html"))
    category_labels = {path.parent.name: page_label(path) for path in category_paths}
    series_labels = {path.parent.name: page_label(path) for path in series_paths}

    ordered_event_ids = sorted(
        event_ids,
        key=lambda event_id: (
            parse_time(by_id.get(event_id, {}).get("starts_at")) is None,
            parse_time(by_id.get(event_id, {}).get("starts_at")) or parse_time("9999-12-31T00:00:00Z"),
            event_id,
        ),
    )

    root_path = public_root / "index.html"
    root = root_path.read_text(encoding="utf-8")
    category_items = "".join(
        f'<li><a href="categories/{esc(category_id)}/">{esc(label)}</a></li>'
        for category_id, label in sorted(category_labels.items())
    )
    series_items = "".join(
        f'<li><a href="series/{esc(series_id)}/">{esc(label)}</a></li>'
        for series_id, label in sorted(series_labels.items(), key=lambda item: item[1])
    )
    hubs = (
        '<section class="search-entry" aria-labelledby="crawl-hubs-title">'
        '<div class="eyebrow">DISCOVER BY TOPIC</div>'
        '<h2 id="crawl-hubs-title">カテゴリ・定期イベントから探す</h2>'
        f'<h3>カテゴリ</h3><ul>{category_items}</ul>'
        f'<h3>定期イベント</h3><ul>{series_items}</ul>'
        '</section>'
    )
    root = replace_block(root, ROOT_HUB_START, ROOT_HUB_END, hubs, "<footer>")

    existing_root_ids = set(re.findall(r'href="events/([^/]+)/"', root))
    remaining = [event_id for event_id in ordered_event_ids if event_id not in existing_root_ids]
    remaining_items = "".join(
        '<li><a href="events/{id}/" data-track="event_detail_open" data-event-id="{id}" '
        'data-category="{category}">{title}</a></li>'.format(
            id=esc(event_id),
            category=esc(by_id.get(event_id, {}).get("category")),
            title=esc(by_id.get(event_id, {}).get("canonical_name") or by_id.get(event_id, {}).get("title") or event_id),
        )
        for event_id in remaining
    )
    all_events = (
        '<details class="search-entry"><summary>すべてのイベント詳細を開く'
        f'（残り{len(remaining)}件）</summary><ul>{remaining_items}</ul></details>'
    )
    root = replace_block(root, ROOT_EVENTS_START, ROOT_EVENTS_END, all_events, "<footer>")
    root_path.write_text(root, encoding="utf-8")

    category_ids = sorted(category_labels)
    category_related_links = 0
    for index, category_id in enumerate(category_ids):
        path = public_root / "categories" / category_id / "index.html"
        text = path.read_text(encoding="utf-8")
        related = ""
        if len(category_ids) > 1:
            related_id = category_ids[(index + 1) % len(category_ids)]
            related = f'<a href="../{esc(related_id)}/">関連カテゴリ: {esc(category_labels[related_id])}</a>'
            category_related_links += 1
        text = replace_block(text, CATEGORY_LINK_START, CATEGORY_LINK_END, related, "</nav>")
        path.write_text(text, encoding="utf-8")

    events_by_category: dict[str, list[str]] = defaultdict(list)
    for event_id in ordered_event_ids:
        category = str(by_id.get(event_id, {}).get("category") or "")
        events_by_category[category].append(event_id)

    event_category_links = 0
    event_related_links = 0
    for event_id in ordered_event_ids:
        path = public_root / "events" / event_id / "index.html"
        text = path.read_text(encoding="utf-8")
        event = by_id.get(event_id, {})
        category = str(event.get("category") or "")
        links: list[str] = []
        if category in category_labels:
            links.append(f'<a href="../../categories/{esc(category)}/">カテゴリを見る</a>')
            event_category_links += 1
        peers = events_by_category.get(category, [])
        if len(peers) > 1:
            position = peers.index(event_id)
            related_id = peers[(position + 1) % len(peers)]
            links.append(f'<a href="../{esc(related_id)}/">関連イベントを見る</a>')
            event_related_links += 1
        text = replace_block(text, EVENT_LINKS_START, EVENT_LINKS_END, "".join(links), "</nav>")
        path.write_text(text, encoding="utf-8")

    return {
        "root_event_links": len(ordered_event_ids),
        "root_category_links": len(category_ids),
        "root_series_links": len(series_labels),
        "event_category_links": event_category_links,
        "event_related_links": event_related_links,
        "category_related_links": category_related_links,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-root", type=Path, default=Path("public"))
    args = parser.parse_args()
    print(json.dumps(render(args.public_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
