from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

ONTOLOGY_PATH = Path("config/event_ontology.json")
EVENTS_PATH = Path("public/events.json")
HEALTH_PATH = Path("public/health.json")
PUBLIC_ONTOLOGY_PATH = Path("public/event-ontology.json")
AUDIT_PATH = Path("public/ontology-match-audit.json")


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


def select_entry(event: dict[str, Any], entries: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str, list[str]]:
    scored: list[tuple[int, dict[str, Any], list[str]]] = []
    for entry in entries:
        score, reasons = match_score(event, entry)
        if score:
            scored.append((score, entry, reasons))
    if not scored:
        return None, "unmatched", []
    scored.sort(key=lambda item: (-item[0], str(item[1].get("canonical_id"))))
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None, "ambiguous", [str(item[1].get("canonical_id")) for item in scored if item[0] == scored[0][0]]
    return scored[0][1], "matched", scored[0][2]


def official_links(event: dict[str, Any], entry: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    source_url = str(event.get("url") or "").strip()
    if source_url:
        rows.append({"label": "公式告知・参加方法", "url": source_url, "kind": "announcement"})
    for item in entry.get("official_links", []):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url.startswith("https://"):
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


def enrich_event(event: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    result = dict(event)
    details = {
        "participation_method": entry.get("participation_method"),
        "event_format": entry.get("event_format"),
        "audience": entry.get("audience"),
    }
    details = {key: str(value) for key, value in details.items() if str(value or "").strip()}
    links = official_links(event, entry)
    result["ontology_id"] = str(entry["canonical_id"])
    result["canonical_name"] = str(entry.get("canonical_name") or event.get("title") or "")
    result["official_links"] = links
    result.update(details)
    if not result.get("location") and entry.get("default_location"):
        result["location"] = entry["default_location"]
    if not result.get("url") and links:
        result["url"] = links[0]["url"]
    tags = {str(value) for value in result.get("tags", []) if str(value).strip()}
    tags.update(str(value) for value in entry.get("tags", []) if str(value).strip())
    tags.add("オントロジー補完")
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


def main() -> int:
    ontology = read_json(ONTOLOGY_PATH)
    entries = [item for item in ontology.get("entries", []) if isinstance(item, dict)]
    payload = read_json(EVENTS_PATH)
    events = [item for item in payload.get("events", []) if isinstance(item, dict)]

    enriched: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    matched = ambiguous = 0
    for event in events:
        entry, status, evidence = select_entry(event, entries)
        if entry:
            matched += 1
            event = enrich_event(event, entry)
            audit_rows.append(
                {
                    "event_id": event.get("id"),
                    "title": event.get("title"),
                    "status": status,
                    "ontology_id": entry.get("canonical_id"),
                    "evidence": evidence,
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

    payload["events"] = enriched
    payload["count"] = len(enriched)
    write_json(EVENTS_PATH, payload)
    write_json(PUBLIC_ONTOLOGY_PATH, ontology)
    write_json(
        AUDIT_PATH,
        {
            "schema_version": "1.0",
            "ontology_entries": len(entries),
            "event_count": len(events),
            "matched_events": matched,
            "unmatched_events": len(events) - matched - ambiguous,
            "ambiguous_events": ambiguous,
            "matches": audit_rows,
        },
    )

    if HEALTH_PATH.exists():
        health = read_json(HEALTH_PATH)
        health["ontology"] = {
            "entries": len(entries),
            "matched_events": matched,
            "unmatched_events": len(events) - matched - ambiguous,
            "ambiguous_events": ambiguous,
            "status": "ok" if ambiguous == 0 else "degraded",
        }
        write_json(HEALTH_PATH, health)
    print(f"ontology: entries={len(entries)} matched={matched} ambiguous={ambiguous}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
