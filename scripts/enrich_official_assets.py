from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

EVENTS_PATH = Path("public/events.json")
CACHE_PATH = Path("data/official_asset_cache.json")
AUDIT_PATH = Path("public/official-asset-audit.json")
SYNDICATION_URL = "https://cdn.syndication.twimg.com/tweet-result"
X_STATUS_RE = re.compile(r"https://(?:www\.)?(?:x|twitter)\.com/([^/?#]+)/status/(\d+)", re.I)
HANDLE_RE = re.compile(r"^@?([A-Za-z0-9_]{1,15})$")
BLOCKED_WEB_HOSTS = {
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "t.co",
    "search.yahoo.co.jp",
    "vrchat.com",
    "www.vrchat.com",
}


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_x_identity(event: dict[str, Any]) -> tuple[str | None, str | None]:
    for value in (event.get("url"), *(row.get("url") for row in event.get("official_links", []) if isinstance(row, dict))):
        match = X_STATUS_RE.search(str(value or ""))
        if match:
            return match.group(1), match.group(2)
    organizer = str(event.get("organizer") or "").strip()
    match = HANDLE_RE.fullmatch(organizer)
    return (match.group(1), None) if match else (None, None)


def canonical_https(url: str | None) -> str | None:
    value = str(url or "").strip()
    if not value.startswith("https://"):
        return None
    parsed = urlparse(value)
    if not parsed.hostname:
        return None
    return urlunparse(("https", parsed.netloc.lower(), parsed.path, "", parsed.query, ""))


def webp_image_url(url: str | None, *, profile: bool = False) -> str | None:
    value = canonical_https(url)
    if not value:
        return None
    parsed = urlparse(value)
    host = parsed.hostname or ""
    if host != "pbs.twimg.com":
        return value if parsed.path.lower().endswith(".webp") else None
    path = parsed.path
    if profile:
        path = re.sub(r"_(?:normal|bigger|mini)(\.[A-Za-z0-9]+)$", r"\1", path)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["format"] = "webp"
    query["name"] = "200x200" if profile else "small"
    return urlunparse(("https", parsed.netloc.lower(), path, "", urlencode(query), ""))


def external_website(payload: dict[str, Any]) -> str | None:
    candidates: list[str] = []
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    for value in (user.get("url"), payload.get("card", {}).get("url") if isinstance(payload.get("card"), dict) else None):
        if value:
            candidates.append(str(value))
    for owner in (user, payload):
        entities = owner.get("entities") if isinstance(owner, dict) else None
        if not isinstance(entities, dict):
            continue
        for section in entities.values():
            if not isinstance(section, dict):
                continue
            for row in section.get("urls", []):
                if isinstance(row, dict):
                    candidates.extend(str(row.get(key) or "") for key in ("expanded_url", "url"))
    for candidate in candidates:
        url = canonical_https(candidate)
        if not url:
            continue
        host = (urlparse(url).hostname or "").lower()
        if host not in BLOCKED_WEB_HOSTS:
            return url
    return None


def assets_from_payload(payload: dict[str, Any], handle: str) -> dict[str, Any]:
    media: list[str] = []
    for row in payload.get("mediaDetails", []):
        if isinstance(row, dict):
            value = webp_image_url(row.get("media_url_https") or row.get("media_url"))
            if value:
                media.append(value)
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    profile_image = webp_image_url(user.get("profile_image_url_https") or user.get("profile_image_url"), profile=True)
    return {
        "official_x_url": f"https://x.com/{handle}",
        "official_website_url": external_website(payload),
        "image_url": media[0] if media else profile_image,
        "image_kind": "post_media" if media else ("organizer_profile" if profile_image else None),
        "evidence": "x_syndication",
    }


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def enrich_event(event: dict[str, Any], cached: dict[str, Any] | None) -> dict[str, Any]:
    row = dict(event)
    handle, status_id = parse_x_identity(row)
    assets = dict(cached or {})
    if handle and not assets.get("official_x_url"):
        assets["official_x_url"] = f"https://x.com/{handle}"
    links = [link for link in row.get("official_links", []) if isinstance(link, dict) and canonical_https(link.get("url"))]
    known = {str(link.get("url")) for link in links}
    announcement = canonical_https(row.get("url"))
    additions = [
        (announcement, "公式告知", "announcement"),
        (assets.get("official_x_url"), "公式X", "official_x"),
        (assets.get("official_website_url"), "公式Web", "official_web"),
    ]
    for url, label, kind in additions:
        if url and url not in known:
            links.append({"url": url, "label": label, "kind": kind, "evidence": assets.get("evidence") or "source_record"})
            known.add(url)
    row["official_links"] = links[:6]
    row["official_x_url"] = assets.get("official_x_url")
    row["official_website_url"] = assets.get("official_website_url")
    image = assets.get("image_url") or webp_image_url(row.get("image_url"))
    row["image_url"] = image
    row["image_kind"] = assets.get("image_kind") if image else None
    row["asset_enrichment"] = {
        "status": "enriched" if any((row.get("official_x_url"), row.get("official_website_url"), image)) else "unresolved",
        "evidence": assets.get("evidence") or ("source_record" if announcement else None),
        "x_status_id": status_id,
    }
    return row


def main() -> int:
    document = load_json(EVENTS_PATH, {})
    events = document.get("events", [])
    cache_doc = load_json(CACHE_PATH, {"schema_version": "1.0", "items": {}})
    cache: dict[str, Any] = cache_doc.setdefault("items", {})
    identities: dict[str, str] = {}
    for event in events:
        handle, status_id = parse_x_identity(event)
        if handle and status_id:
            identities.setdefault(status_id, handle)

    fetched = 0
    failures: Counter[str] = Counter()
    with httpx.Client(timeout=12, follow_redirects=True, headers={"User-Agent": "cast-event-cal/2 official-asset-enricher"}) as client:
        for status_id, handle in identities.items():
            if status_id in cache:
                continue
            try:
                response = client.get(SYNDICATION_URL, params={"id": status_id, "lang": "ja"})
                response.raise_for_status()
                payload = response.json()
                cache[status_id] = {**assets_from_payload(payload, handle), "fetched_at": now_iso()}
                fetched += 1
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                failures[type(exc).__name__] += 1
                cache[status_id] = {
                    "official_x_url": f"https://x.com/{handle}",
                    "official_website_url": None,
                    "image_url": None,
                    "image_kind": None,
                    "evidence": "x_identity_only",
                    "fetched_at": now_iso(),
                }

    enriched = []
    for event in events:
        _handle, status_id = parse_x_identity(event)
        enriched.append(enrich_event(event, cache.get(status_id) if status_id else None))
    document["events"] = enriched
    document["count"] = len(enriched)
    document["official_asset_enriched_at"] = now_iso()
    EVENTS_PATH.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CACHE_PATH.write_text(json.dumps(cache_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = {
        "events": len(enriched),
        "official_x": sum(bool(row.get("official_x_url")) for row in enriched),
        "official_web": sum(bool(row.get("official_website_url")) for row in enriched),
        "webp_image": sum(str(row.get("image_url") or "").lower().find("format=webp") >= 0 or str(row.get("image_url") or "").lower().endswith(".webp") for row in enriched),
        "post_media": sum(row.get("image_kind") == "post_media" for row in enriched),
        "profile_image": sum(row.get("image_kind") == "organizer_profile" for row in enriched),
        "unresolved": sum(row.get("asset_enrichment", {}).get("status") == "unresolved" for row in enriched),
    }
    audit = {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "policy": "source-identity-and-x-syndication-only",
        "counts": counts,
        "network_fetches": fetched,
        "fetch_failures": dict(failures),
        "sample": [
            {
                "id": row.get("id"),
                "title": row.get("canonical_name") or row.get("title"),
                "official_x_url": row.get("official_x_url"),
                "official_website_url": row.get("official_website_url"),
                "image_url": row.get("image_url"),
                "image_kind": row.get("image_kind"),
            }
            for row in enriched
            if row.get("official_x_url") or row.get("official_website_url") or row.get("image_url")
        ][:20],
    }
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
