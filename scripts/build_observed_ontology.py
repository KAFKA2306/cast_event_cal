from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CONFIG = Path("config/event_ontology.json")
CATEGORY_CONFIG = Path("config/category_ontology.json")
EVENTS = Path("public/events.json")
OUTPUT = Path("public/event-ontology.json")


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def https(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text.startswith("https://") or not urlparse(text).hostname:
        return None
    return text


def entity_key(event: dict[str, Any]) -> str | None:
    official_x = https(event.get("official_x_url"))
    if official_x:
        return official_x.rstrip("/").lower()
    organizer = str(event.get("organizer") or "").strip()
    return organizer.casefold() if organizer else None


def counted(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    values = Counter(str(row.get(field)) for row in rows if str(row.get(field) or "").strip())
    return dict(sorted(values.items(), key=lambda item: (-item[1], item[0])))


def dominant(distribution: dict[str, int], total: int) -> dict[str, Any] | None:
    if not distribution or total <= 0:
        return None
    value, count = next(iter(distribution.items()))
    return {
        "value": value,
        "count": count,
        "share": round(count / total, 3),
    }


def build() -> dict[str, Any]:
    curated = read(CONFIG)
    category_ontology = read(CATEGORY_CONFIG)
    event_doc = read(EVENTS)
    events = [row for row in event_doc.get("events", []) if isinstance(row, dict)]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        key = entity_key(event)
        if key:
            groups[key].append(event)

    observed: list[dict[str, Any]] = []
    for key, rows in groups.items():
        rows.sort(key=lambda row: str(row.get("starts_at") or ""), reverse=True)
        first = rows[0]
        links: dict[str, dict[str, str]] = {}
        for row in rows:
            for candidate in row.get("official_links", []):
                if not isinstance(candidate, dict):
                    continue
                url = https(candidate.get("url"))
                if not url:
                    continue
                links[url] = {
                    "url": url,
                    "label": str(candidate.get("label") or "公式リンク"),
                    "kind": str(candidate.get("kind") or "official"),
                }
        official_x = https(first.get("official_x_url"))
        official_web = next(
            (https(row.get("official_website_url")) for row in rows if https(row.get("official_website_url"))),
            None,
        )
        image_url = next((https(row.get("image_url")) for row in rows if https(row.get("image_url"))), None)
        category_distribution = counted(rows, "category")
        subcategory_distribution = counted(rows, "category_detail")
        mode_distribution = counted(rows, "event_mode")
        observed.append(
            {
                "entity_id": key,
                "organizer": str(first.get("organizer") or ""),
                "official_x_url": official_x,
                "official_website_url": official_web,
                "image_url": image_url,
                "image_kind": next((row.get("image_kind") for row in rows if row.get("image_url")), None),
                "observed_event_count": len(rows),
                "latest_observed_start": str(first.get("starts_at") or ""),
                "sample_event_ids": [str(row.get("id")) for row in rows[:5] if row.get("id")],
                "sample_titles": [str(row.get("canonical_name") or row.get("title") or "") for row in rows[:3]],
                "category_distribution": category_distribution,
                "dominant_category": dominant(category_distribution, len(rows)),
                "subcategory_distribution": subcategory_distribution,
                "event_mode_distribution": mode_distribution,
                "official_links": sorted(links.values(), key=lambda row: (row["kind"], row["url"])),
            }
        )
    observed.sort(key=lambda row: (-int(row["observed_event_count"]), str(row["entity_id"])))

    category_labels = {
        str(row.get("id")): str(row.get("label") or row.get("id"))
        for row in category_ontology.get("categories", [])
        if isinstance(row, dict) and row.get("id")
    }
    return {
        "schema_version": "3.0",
        "generated_at": now_iso(),
        "source_event_generated_at": event_doc.get("generated_at"),
        "source_event_count": int(event_doc.get("count") or len(events)),
        "matching_policy": curated.get("matching_policy", {}),
        "curated_entry_count": len(curated.get("entries", [])),
        "observed_entity_count": len(observed),
        "category_ontology_schema_version": category_ontology.get("schema_version"),
        "category_labels": category_labels,
        "category_breakdown": counted(events, "category"),
        "subcategory_breakdown": counted(events, "category_detail"),
        "event_mode_breakdown": counted(events, "event_mode"),
        "classification_source_breakdown": counted(events, "category_source"),
        "entries": curated.get("entries", []),
        "observed_entities": observed,
    }


def main() -> int:
    payload = build()
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"observed ontology: curated={payload['curated_entry_count']} "
        f"observed={payload['observed_entity_count']} events={payload['source_event_count']} "
        f"categories={payload['category_breakdown']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
