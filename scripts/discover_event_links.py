from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

EVENTS = Path("public/events.json")
AUDIT = Path("public/event-link-audit.json")
URL_RE = re.compile(r"https://[^\s<>\]\[(){}\"'、。]+", re.I)
SHORTENERS = {"t.co", "bit.ly", "tinyurl.com", "is.gd", "x.gd", "onl.sc"}
BLOCKED = {"pbs.twimg.com", "search.yahoo.co.jp"}
PRIORITY = {
    "application": 0,
    "vrchat_group": 1,
    "vrchat_world": 2,
    "join": 3,
    "announcement": 4,
    "official_web": 5,
    "stream": 6,
    "community": 7,
    "official_x": 8,
    "related_web": 9,
}


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical(url: Any) -> str | None:
    value = str(url or "").strip().rstrip(".,;:!?)】」』")
    if not value.startswith("https://"):
        return None
    parsed = urlparse(value)
    if not parsed.hostname:
        return None
    return value


def classify(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    if host in {"forms.gle", "docs.google.com"} and ("form" in path or host == "forms.gle"):
        return "application", "応募・申込"
    if host in {"vrchat.com", "www.vrchat.com"} and "/home/group/" in path:
        return "vrchat_group", "VRChat Group"
    if host in {"vrchat.com", "www.vrchat.com"} and "/home/world/" in path:
        return "vrchat_world", "VRChat World"
    if host in {"discord.gg", "discord.com"}:
        return "community", "Discord"
    if host in {"youtube.com", "www.youtube.com", "youtu.be", "twitch.tv", "www.twitch.tv"}:
        return "stream", "配信・動画"
    if host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
        if "/status/" in path:
            return "announcement", "公式告知"
        return "official_x", "公式X"
    return "related_web", "関連Web"


def source_urls(event: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for field in ("url", "official_x_url", "official_website_url"):
        url = canonical(event.get(field))
        if url:
            rows.append((url, f"field:{field}"))
    for field in ("official_links", "related_links"):
        values = event.get(field) if isinstance(event.get(field), list) else []
        for row in values:
            if isinstance(row, dict):
                url = canonical(row.get("url"))
                if url:
                    rows.append((url, f"field:{field}"))
    for field in ("title", "description", "participation_method", "location"):
        for raw in URL_RE.findall(str(event.get(field) or "")):
            url = canonical(raw)
            if url:
                rows.append((url, f"text:{field}"))
    return rows


def resolve(client: httpx.Client, url: str, cache: dict[str, tuple[str, str]] | None = None) -> tuple[str, str]:
    if cache is not None and url in cache:
        return cache[url]
    host = (urlparse(url).hostname or "").lower()
    if host not in SHORTENERS:
        result = (url, "direct")
    elif os.getenv("EVENT_LINK_SKIP_SHORTENER_RESOLUTION") == "1":
        result = (url, "unresolved_shortener")
    else:
        try:
            response = client.head(url, follow_redirects=True)
            if response.status_code >= 400:
                response = client.get(url, follow_redirects=True)
            target = canonical(str(response.url))
            result = ((target or url), "redirect")
        except httpx.HTTPError:
            result = (url, "unresolved_shortener")
    if cache is not None:
        cache[url] = result
    return result


def enrich(event: dict[str, Any], client: httpx.Client, resolution_cache: dict[str, tuple[str, str]] | None = None) -> dict[str, Any]:
    output = dict(event)
    discovered: dict[str, dict[str, str]] = {}
    for raw, evidence in source_urls(event):
        resolved, resolution = resolve(client, raw, resolution_cache)
        host = (urlparse(resolved).hostname or "").lower()
        if host in BLOCKED:
            continue
        kind, label = classify(resolved)
        current = discovered.get(resolved)
        row = {
            "url": resolved,
            "kind": kind,
            "label": label,
            "evidence": evidence,
            "resolution": resolution,
        }
        if current is None or PRIORITY[kind] < PRIORITY[current["kind"]]:
            discovered[resolved] = row
    links = sorted(discovered.values(), key=lambda row: (PRIORITY[row["kind"]], row["url"]))
    official = [row for row in links if row["kind"] in {"application", "vrchat_group", "vrchat_world", "announcement", "official_web", "official_x"}]
    related = [row for row in links if row not in official]
    output["official_links"] = official[:10]
    output["related_links"] = related[:10]
    click = next((row for row in links if row["kind"] in {"application", "vrchat_group", "vrchat_world", "join", "announcement", "official_web"}), None)
    output["primary_action_url"] = click["url"] if click else canonical(event.get("url"))
    output["primary_action_kind"] = click["kind"] if click else "announcement"
    output["link_discovery"] = {"count": len(links), "generated_at": now_iso()}
    return output


def main() -> int:
    doc = json.loads(EVENTS.read_text(encoding="utf-8"))
    counts: Counter[str] = Counter()
    rows = []
    resolution_cache: dict[str, tuple[str, str]] = {}
    with httpx.Client(timeout=3, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 cast-event-cal/2"}) as client:
        for event in doc.get("events", []):
            row = enrich(event, client, resolution_cache)
            rows.append(row)
            for link in row.get("official_links", []) + row.get("related_links", []):
                counts[str(link.get("kind"))] += 1
    doc["events"] = rows
    doc["count"] = len(rows)
    doc["link_discovered_at"] = now_iso()
    EVENTS.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "event_count": len(rows),
        "link_kind_counts": dict(sorted(counts.items())),
        "events_with_primary_action": sum(bool(row.get("primary_action_url")) for row in rows),
        "events_with_application": sum(any(link.get("kind") == "application" for link in row.get("official_links", [])) for row in rows),
        "events_with_vrchat_group": sum(any(link.get("kind") == "vrchat_group" for link in row.get("official_links", [])) for row in rows),
        "resolution_cache_size": len(resolution_cache),
        "shortener_resolution_skipped": os.getenv("EVENT_LINK_SKIP_SHORTENER_RESOLUTION") == "1",
        "sample": [
            {
                "id": row.get("id"),
                "title": row.get("canonical_name") or row.get("title"),
                "primary_action_url": row.get("primary_action_url"),
                "primary_action_kind": row.get("primary_action_kind"),
                "official_links": row.get("official_links", [])[:5],
            }
            for row in rows if row.get("primary_action_url")
        ][:25],
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit["link_kind_counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
