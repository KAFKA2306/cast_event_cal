from __future__ import annotations

import html
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from scripts.validate_public_image_assets import sanitize_event_images, write_audit

EVENTS = Path("public/events.json")
AUDIT = Path("public/vrchat-group-asset-audit.json")
GROUP_RE = re.compile(r"^https://(?:www\.)?vrchat\.com/home/group/(grp_[A-Za-z0-9-]+)(?:[/?#].*)?$", re.I)
META_RE = re.compile(
    r'<meta\s+(?:property|name)=["\'](?:og:image|twitter:image)["\']\s+content=["\']([^"\']+)["\']',
    re.I,
)
META_RE_REVERSED = re.compile(
    r'<meta\s+content=["\']([^"\']+)["\']\s+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    re.I,
)


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def group_url(event: dict[str, Any]) -> str | None:
    links = event.get("official_links") if isinstance(event.get("official_links"), list) else []
    for row in links:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "")
        if str(row.get("kind") or "") == "vrchat_group" and GROUP_RE.match(url):
            return url.split("?", 1)[0].split("#", 1)[0]
    for field in ("primary_action_url", "url"):
        url = str(event.get(field) or "")
        if GROUP_RE.match(url):
            return url.split("?", 1)[0].split("#", 1)[0]
    return None


def extract_group_image(page_html: str) -> str | None:
    for pattern in (META_RE, META_RE_REVERSED):
        match = pattern.search(page_html)
        if not match:
            continue
        url = html.unescape(match.group(1)).strip()
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.hostname:
            return url
    return None


def main() -> int:
    document = json.loads(EVENTS.read_text(encoding="utf-8"))
    events = [row for row in document.get("events", []) if isinstance(row, dict)]
    urls = sorted({url for row in events if (url := group_url(row))})
    images: dict[str, str | None] = {}
    failures: Counter[str] = Counter()
    with httpx.Client(timeout=12, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 cast-event-cal/2"}) as client:
        for url in urls:
            try:
                response = client.get(url)
                response.raise_for_status()
                images[url] = extract_group_image(response.text)
                if not images[url]:
                    failures["missing_meta_image"] += 1
            except httpx.HTTPError as exc:
                images[url] = None
                failures[type(exc).__name__] += 1

    enriched = []
    for event in events:
        row = dict(event)
        url = group_url(row)
        image = images.get(url) if url else None
        row["vrchat_group_url"] = url
        row["vrchat_group_image_url"] = image
        if image:
            row["preferred_image_url"] = image
            row["preferred_image_kind"] = "vrchat_group"
        else:
            row["preferred_image_url"] = row.get("image_url")
            row["preferred_image_kind"] = row.get("image_kind")
        enriched.append(row)

    enriched, image_audit = sanitize_event_images(enriched)
    write_audit(image_audit)
    document["events"] = enriched
    document["vrchat_group_assets_enriched_at"] = now_iso()
    document["image_reachability_validated_at"] = image_audit["generated_at"]
    EVENTS.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "group_url_count": len(urls),
        "group_image_count": sum(bool(row.get("vrchat_group_image_url")) for row in enriched),
        "events_with_group_url": sum(bool(row.get("vrchat_group_url")) for row in enriched),
        "events_with_group_image": sum(bool(row.get("vrchat_group_image_url")) for row in enriched),
        "failures": dict(failures),
        "image_reachability": {
            "checked_url_count": image_audit["checked_url_count"],
            "failed_url_count": image_audit["failed_url_count"],
            "events_degraded": image_audit["events_degraded"],
        },
        "sample": [
            {
                "id": row.get("id"),
                "title": row.get("canonical_name") or row.get("title"),
                "vrchat_group_url": row.get("vrchat_group_url"),
                "vrchat_group_image_url": row.get("vrchat_group_image_url"),
            }
            for row in enriched
            if row.get("vrchat_group_url")
        ][:25],
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: audit[key]
                for key in ("group_url_count", "group_image_count", "events_with_group_url", "events_with_group_image")
            }
            | {"image_reachability": audit["image_reachability"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
