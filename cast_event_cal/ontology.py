from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from cast_event_cal.categories import classify_events, load_category_ontology

ONTOLOGY_PATH = Path("config/event_ontology.json")
EVENTS_PATH = Path("public/events.json")
HEALTH_PATH = Path("public/health.json")
PUBLIC_ONTOLOGY_PATH = Path("public/event-ontology.json")
PUBLIC_CATEGORY_ONTOLOGY_PATH = Path("public/category-ontology.json")
AUDIT_PATH = Path("public/ontology-match-audit.json")

SERIES_TYPES = {"recurring", "irregular", "one_off"}
CURATION_STATUS = "human_curated"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龠@]+", "", text)


def text_contains(haystack: str, needle: str) -> bool:
    candidate = normalized(needle)
    return bool(candidate) and candidate in normalized(haystack)


def clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def clean_text_list(value: Any, *, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = clean_text(item)
        key = normalized(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        rows.append(text)
        if len(rows) >= limit:
            break
    return rows


def validate_https_url(value: Any) -> str | None:
    url = clean_text(value)
    if not url or not url.startswith("https://"):
        return None
    return url


def validate_ontology(ontology: dict[str, Any]) -> None:
    governance = ontology.get("governance")
    if not isinstance(governance, dict):
        raise ValueError("event ontology governance is required")
    if governance.get("curation_mode") != "human_only":
        raise ValueError("event ontology must remain human-curated")
    if governance.get("automatic_entry_creation") is not False:
        raise ValueError("automatic ontology entry creation must remain disabled")
    if governance.get("automatic_entry_rewrite") is not False:
        raise ValueError("automatic ontology entry rewriting must remain disabled")

    entries = ontology.get("entries")
    if not isinstance(entries, list):
        raise ValueError("event ontology entries must be a list")

    ids: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"event ontology entry {index} must be an object")
        canonical_id = clean_text(entry.get("canonical_id"))
        canonical_name = clean_text(entry.get("canonical_name"))
        if not canonical_id or not canonical_name:
            raise ValueError(f"event ontology entry {index} requires canonical identity")
        if canonical_id in ids:
            raise ValueError(f"duplicate event ontology id: {canonical_id}")
        ids.add(canonical_id)

        curation = entry.get("curation")
        if not isinstance(curation, dict) or curation.get("status") != CURATION_STATUS:
            raise ValueError(f"{canonical_id}: curation.status must be {CURATION_STATUS}")
        if not clean_text(curation.get("reviewed_at")):
            raise ValueError(f"{canonical_id}: curation.reviewed_at is required")
        sources = curation.get("sources")
        if not isinstance(sources, list) or not any(validate_https_url(url) for url in sources):
            raise ValueError(f"{canonical_id}: at least one reviewed https source is required")

        schedule = entry.get("schedule")
        if not isinstance(schedule, dict) or schedule.get("type") not in SERIES_TYPES:
            raise ValueError(f"{canonical_id}: schedule.type must be recurring, irregular, or one_off")
        if not clean_text(schedule.get("label")) or not clean_text(schedule.get("cadence")):
            raise ValueError(f"{canonical_id}: schedule label and cadence are required")

        if not clean_text(entry.get("introduction")):
            raise ValueError(f"{canonical_id}: introduction is required")
        if not clean_text_list(entry.get("highlights"), limit=6):
            raise ValueError(f"{canonical_id}: at least one highlight is required")
        if not clean_text(entry.get("first_time_guide")):
            raise ValueError(f"{canonical_id}: first_time_guide is required")

        for link in entry.get("official_links", []):
            if not isinstance(link, dict) or not validate_https_url(link.get("url")):
                raise ValueError(f"{canonical_id}: official_links must contain verified https URLs")


def match_score(event: dict[str, Any], entry: dict[str, Any]) -> tuple[int, list[str]]:
    title = str(event.get("title") or "")
    description = str(event.get("description") or "")
    organizer = normalized(event.get("organizer"))
    aliases = [str(value) for value in entry.get("aliases", []) if str(value).strip()]
    organizers = {normalized(value) for value in entry.get("organizers", []) if normalized(value)}
    patterns = [str(value) for value in entry.get("required_patterns", []) if str(value).strip()]

    reasons: list[str] = []
    alias_match = any(text_contains(title, alias) or text_contains(description, alias) for alias in aliases)
    organizer_match = bool(organizer and organizer in organizers)
    pattern_match = bool(patterns) and all(
        text_contains(f"{title} {description}", pattern) for pattern in patterns
    )

    score = 0
    if alias_match:
        score += 5
        reasons.append("alias")
    if organizer_match:
        score += 3
        reasons.append("organizer")
    if pattern_match:
        score += 2
        reasons.append("required_patterns")

    # Fail closed: a pattern alone is never enough. Require an alias, or the
    # combination of exact organizer and all required patterns.
    if not alias_match and not (organizer_match and pattern_match):
        return 0, []
    return score, reasons


def select_entry(
    event: dict[str, Any], entries: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, str, list[str]]:
    scored: list[tuple[int, dict[str, Any], list[str]]] = []
    for entry in entries:
        score, reasons = match_score(event, entry)
        if score:
            scored.append((score, entry, reasons))
    if not scored:
        return None, "unmatched", []
    scored.sort(key=lambda item: (-item[0], str(item[1].get("canonical_id"))))
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None, "ambiguous", [
            str(item[1].get("canonical_id")) for item in scored if item[0] == scored[0][0]
        ]
    return scored[0][1], "matched", scored[0][2]


def official_links(event: dict[str, Any], entry: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    source_url = validate_https_url(event.get("url"))
    if source_url:
        rows.append({"label": "公式告知・参加方法", "url": source_url, "kind": "announcement"})
    for item in entry.get("official_links", []):
        if not isinstance(item, dict):
            continue
        url = validate_https_url(item.get("url"))
        if not url:
            continue
        rows.append(
            {
                "label": str(item.get("label") or "公式リンク"),
                "url": url,
                "kind": str(item.get("kind") or "official"),
            }
        )
    selected: dict[str, dict[str, str]] = {}
    for row in rows:
        selected[row["url"]] = row
    return list(selected.values())


def series_profile(entry: dict[str, Any]) -> dict[str, Any]:
    schedule = entry.get("schedule") if isinstance(entry.get("schedule"), dict) else {}
    curation = entry.get("curation") if isinstance(entry.get("curation"), dict) else {}
    image = entry.get("official_image") if isinstance(entry.get("official_image"), dict) else {}

    profile: dict[str, Any] = {
        "ontology_id": str(entry["canonical_id"]),
        "name": str(entry.get("canonical_name") or ""),
        "schedule": {
            key: value
            for key, value in {
                "type": clean_text(schedule.get("type")),
                "label": clean_text(schedule.get("label")),
                "cadence": clean_text(schedule.get("cadence")),
                "note": clean_text(schedule.get("note")),
            }.items()
            if value
        },
        "introduction": clean_text(entry.get("introduction")),
        "highlights": clean_text_list(entry.get("highlights"), limit=6),
        "first_time_guide": clean_text(entry.get("first_time_guide")),
        "curation": {
            "status": clean_text(curation.get("status")),
            "reviewed_at": clean_text(curation.get("reviewed_at")),
        },
    }

    image_url = validate_https_url(image.get("url"))
    if image_url:
        profile["official_image"] = {
            "url": image_url,
            "alt": clean_text(image.get("alt")) or str(entry.get("canonical_name") or "公式画像"),
            "kind": clean_text(image.get("kind")) or "official_image",
        }
    return profile


def enrich_event(event: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    result = dict(event)
    details = {
        "participation_method": entry.get("participation_method"),
        "event_format": entry.get("event_format"),
        "audience": entry.get("audience"),
    }
    details = {key: str(value) for key, value in details.items() if str(value or "").strip()}
    links = official_links(event, entry)
    profile = series_profile(entry)
    result["ontology_id"] = str(entry["canonical_id"])
    result["canonical_name"] = str(entry.get("canonical_name") or event.get("title") or "")
    result["official_links"] = links
    result["series_profile"] = profile
    result.update(details)
    if entry.get("category"):
        result["ontology_category"] = str(entry["category"])
    if entry.get("subcategory"):
        result["ontology_subcategory"] = str(entry["subcategory"])
    if not result.get("location") and entry.get("default_location"):
        result["location"] = entry["default_location"]
    if not result.get("url") and links:
        result["url"] = links[0]["url"]
    tags = {str(value) for value in result.get("tags", []) if str(value).strip()}
    tags.update(str(value) for value in entry.get("tags", []) if str(value).strip())
    tags.add("オントロジー補完")
    schedule_label = profile.get("schedule", {}).get("label")
    if schedule_label:
        tags.add(str(schedule_label))
    result["tags"] = sorted(tags)

    detail_lines = []
    if details.get("participation_method"):
        detail_lines.append(f"参加方法: {details['participation_method']}")
    if details.get("event_format"):
        detail_lines.append(f"開催形式: {details['event_format']}")
    if details.get("audience"):
        detail_lines.append(f"対象: {details['audience']}")
    description = str(result.get("description") or "").strip()
    supplement = " / ".join(detail_lines)
    if supplement and supplement not in description:
        result["description"] = f"{description} {supplement}".strip()
    return result


def compact_category_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if key != "organizer_profiles"}


def main() -> int:
    ontology = read_json(ONTOLOGY_PATH)
    validate_ontology(ontology)
    category_ontology = load_category_ontology()
    entries = [item for item in ontology.get("entries", []) if isinstance(item, dict)]
    payload = read_json(EVENTS_PATH)
    events = [item for item in payload.get("events", []) if isinstance(item, dict)]

    enriched: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    matched = ambiguous = 0
    matched_series: dict[str, int] = {}
    for event in events:
        entry, status, evidence = select_entry(event, entries)
        if entry:
            matched += 1
            ontology_id = str(entry.get("canonical_id"))
            matched_series[ontology_id] = matched_series.get(ontology_id, 0) + 1
            event = enrich_event(event, entry)
            audit_rows.append(
                {
                    "event_id": event.get("id"),
                    "title": event.get("title"),
                    "status": status,
                    "ontology_id": ontology_id,
                    "evidence": evidence,
                    "profile_attached": True,
                }
            )
        elif status == "ambiguous":
            ambiguous += 1
            audit_rows.append(
                {
                    "event_id": event.get("id"),
                    "title": event.get("title"),
                    "status": status,
                    "candidates": evidence,
                }
            )
        enriched.append(event)

    classified, category_summary, category_audit = classify_events(enriched, category_ontology)
    payload["events"] = classified
    payload["count"] = len(classified)
    payload["event_ontology_schema_version"] = ontology.get("schema_version")
    payload["category_ontology_schema_version"] = category_ontology.get("schema_version")
    write_json(EVENTS_PATH, payload)
    write_json(PUBLIC_ONTOLOGY_PATH, ontology)
    write_json(PUBLIC_CATEGORY_ONTOLOGY_PATH, category_ontology)
    write_json(
        AUDIT_PATH,
        {
            "schema_version": "3.0",
            "ontology_entries": len(entries),
            "curation_mode": ontology.get("governance", {}).get("curation_mode"),
            "event_count": len(events),
            "matched_events": matched,
            "matched_series": matched_series,
            "unmatched_events": len(events) - matched - ambiguous,
            "ambiguous_events": ambiguous,
            "matches": audit_rows,
            "category_classification": compact_category_summary(category_summary),
            "category_review_queue": category_audit,
        },
    )

    if HEALTH_PATH.exists():
        health = read_json(HEALTH_PATH)
        health["ontology"] = {
            "schema_version": ontology.get("schema_version"),
            "curation_mode": ontology.get("governance", {}).get("curation_mode"),
            "entries": len(entries),
            "matched_events": matched,
            "matched_series": len(matched_series),
            "unmatched_events": len(events) - matched - ambiguous,
            "ambiguous_events": ambiguous,
            "status": "ok" if ambiguous == 0 else "degraded",
        }
        health["category_classification"] = compact_category_summary(category_summary)
        write_json(HEALTH_PATH, health)
    print(
        f"ontology: entries={len(entries)} matched={matched} ambiguous={ambiguous} "
        f"series={matched_series} categories={category_summary['category_breakdown']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
