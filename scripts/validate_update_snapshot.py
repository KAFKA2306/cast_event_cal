from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SOURCE_HEALTH_PATHS = {
    "vrchat_calendar_discovery": Path("data/discovery_health.json"),
    "x_curated_events": Path("data/x_discovery_health.json"),
    "yahoo_realtime_events": Path("data/yahoo_realtime_health.json"),
    "external_calendar_events": Path("data/external_discovery_health.json"),
}
VALID_COLLECTION_STATUSES = {"ok", "degraded", "skipped", "error", "failed"}
OPTIONAL_COLLECTION_SOURCES = {"vrchat_calendar_discovery", "x_curated_events", "external_calendar_events"}


class SnapshotValidationError(RuntimeError):
    pass


def load_json(root: Path, path: str | Path) -> Any:
    target = root / path
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotValidationError(f"cannot read valid JSON from {path}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SnapshotValidationError(message)


def parse_instant(value: Any, *, label: str) -> datetime:
    require(isinstance(value, str) and bool(value.strip()), f"{label} has no generated_at")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnapshotValidationError(f"{label} generated_at is not ISO-8601: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def annotation(level: str, title: str, message: str) -> None:
    text = str(message).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{level} title={title}::{text}")


def sync_collection_health(root: Path, *, now: datetime | None = None, max_age: timedelta = timedelta(hours=2)) -> dict[str, Any]:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    health = load_json(root, "public/health.json")
    require(isinstance(health, dict), "public/health.json must be an object")
    sources = health.get("sources")
    require(isinstance(sources, list), "public/health.json sources must be an array")

    seen: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        name = str(source.get("name") or "")
        path = SOURCE_HEALTH_PATHS.get(name)
        if path is None:
            continue
        upstream = load_json(root, path)
        require(isinstance(upstream, dict), f"{path} must be an object")
        status = str(upstream.get("status") or "").strip().lower()
        require(status in VALID_COLLECTION_STATUSES, f"{path} has unsupported status: {status!r}")
        generated_at = parse_instant(upstream.get("generated_at"), label=str(path))
        age = current - generated_at
        require(age <= max_age, f"{path} is stale: generated_at={generated_at.isoformat()} age={age}")
        require(age >= timedelta(minutes=-5), f"{path} generated_at is unexpectedly in the future: {generated_at.isoformat()}")

        source["status"] = status
        source["collection_generated_at"] = upstream.get("generated_at")
        reason = upstream.get("reason")
        if reason:
            source["reason"] = str(reason)
        else:
            source.pop("reason", None)
        if isinstance(upstream.get("event_count"), int):
            source["collection_event_count"] = upstream["event_count"]
        seen.add(name)

        if status != "ok":
            annotation("warning", "collection source", f"{name}: {status} - {reason or 'no reason supplied'}")

    missing = sorted(set(SOURCE_HEALTH_PATHS) - seen)
    require(not missing, f"public/health.json is missing collection sources: {', '.join(missing)}")

    statuses = [str(item.get("status") or "") for item in sources if isinstance(item, dict)]
    ok_count = statuses.count("ok")
    skipped_count = statuses.count("skipped")
    degraded_count = statuses.count("degraded")
    failed_count = sum(status in {"error", "failed"} for status in statuses)
    health["schema_version"] = "1.1"
    health["successful_sources"] = ok_count
    health["skipped_sources"] = skipped_count
    health["degraded_sources"] = degraded_count
    health["failed_sources"] = failed_count
    if failed_count and not ok_count:
        health["status"] = "error"
    elif failed_count or degraded_count or skipped_count:
        health["status"] = "degraded"
    else:
        health["status"] = "ok"

    output = root / "public/health.json"
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(health, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return health


def validate_snapshot(root: Path) -> None:
    yahoo = load_json(root, "data/yahoo_realtime_events.json")
    rejected = load_json(root, "data/yahoo_realtime_rejected.json")
    yahoo_health = load_json(root, "data/yahoo_realtime_health.json")
    history = load_json(root, "public/yahoo-candidate-history.json")
    audit = load_json(root, "public/yahoo-classifier-audit.json")
    registration = load_json(root, "public/registration-count-audit.json")
    events = load_json(root, "public/events.json")
    duplicate_audit = load_json(root, "public/event-duplicate-audit.json")
    assets = load_json(root, "public/official-asset-audit.json")
    links = load_json(root, "public/event-link-audit.json")
    groups = load_json(root, "public/vrchat-group-asset-audit.json")
    ontology = load_json(root, "public/event-ontology.json")
    category_ontology = load_json(root, "public/category-ontology.json")
    ontology_audit = load_json(root, "public/ontology-match-audit.json")
    external = load_json(root, "data/external_discovery_health.json")
    public_health = load_json(root, "public/health.json")

    rows = events.get("events") if isinstance(events, dict) else None
    require(isinstance(rows, list), "public/events.json events must be an array")
    require(events.get("count") == len(rows), "public/events.json count does not match events length")
    require(len(rows) > 0, "public/events.json contains no events")

    require(history.get("candidate_count") == len(history.get("candidates", [])), "Yahoo candidate history count mismatch")
    require(audit.get("classifier_version") == "1.9", "Yahoo classifier audit is not version 1.9")
    require(audit.get("accepted_count") == len(yahoo), "Yahoo accepted count mismatch")
    require(audit.get("rejected_count") == len(rejected), "Yahoo rejected count mismatch")
    require(audit.get("accepted_count", 0) + audit.get("rejected_count", 0) == history.get("candidate_count"), "Yahoo audit does not partition candidate history")
    require(yahoo_health.get("parser_version") == "1.9", "Yahoo health parser version is not 1.9")
    require(yahoo_health.get("status") == "ok", f"Yahoo collection is not healthy: {yahoo_health.get('status')} {yahoo_health.get('reason')}")
    require(yahoo_health.get("queries_failed") == 0, f"Yahoo collection has failed queries: {yahoo_health.get('queries_failed')}")
    require(int(yahoo_health.get("queries_succeeded") or 0) > 0, "Yahoo collection completed without a successful query")

    require(registration.get("schema_version") == "1.0", "registration audit schema mismatch")
    require(registration.get("status") == "ok", "registration audit is not healthy")
    require(registration.get("snapshot_count") == len(registration.get("snapshots", [])), "registration snapshot count mismatch")
    latest = registration.get("latest") or {}
    require(latest.get("calendar_event_count") == events.get("count"), "registration calendar event count mismatch")
    require(latest.get("yahoo_candidate_count") == history.get("candidate_count"), "registration Yahoo candidate count mismatch")
    require(latest.get("yahoo_accepted_count") == len(yahoo), "registration Yahoo accepted count mismatch")
    require(latest.get("yahoo_rejected_count") == len(rejected), "registration Yahoo rejected count mismatch")
    require(latest.get("yahoo_queries_failed") == 0, "registration reports failed Yahoo queries")

    require(duplicate_audit.get("schema_version") == "1.0", "duplicate audit schema mismatch")
    require(duplicate_audit.get("policy_version") == "canonical-occurrence.v1", "duplicate audit policy mismatch")
    require(duplicate_audit.get("event_count_after") == events.get("count"), "duplicate audit output count mismatch")
    require(duplicate_audit.get("event_count_before", -1) >= duplicate_audit.get("event_count_after", 0), "duplicate audit increased event count")
    require(duplicate_audit.get("duplicate_occurrence_count") == duplicate_audit.get("event_count_before") - duplicate_audit.get("event_count_after"), "duplicate audit delta mismatch")

    occurrence_ids = [row.get("occurrence_id") for row in rows if isinstance(row, dict)]
    source_record_ids = [row.get("source_record_id") for row in rows if isinstance(row, dict)]
    require(len(occurrence_ids) == len(rows) and all(occurrence_ids), "one or more events lack occurrence_id")
    require(len(source_record_ids) == len(rows) and all(source_record_ids), "one or more events lack source_record_id")
    require(len(occurrence_ids) == len(set(occurrence_ids)), "occurrence_id values are not unique")

    ics_text = (root / "public/calendar.ics").read_text(encoding="utf-8")
    require("BEGIN:VCALENDAR" in ics_text, "public/calendar.ics is not a calendar")
    ics_uids = [line[4:] for line in ics_text.splitlines() if line.startswith("UID:")]
    require(len(ics_uids) == len(rows), "ICS UID count does not match event count")
    require(len(ics_uids) == len(set(ics_uids)), "ICS UID values are not unique")

    html = (root / "public/index.html").read_text(encoding="utf-8")
    for marker in ("VRChat Event Calendar", "event-media-link", "canonicalLinkKey", "preferredActionUrl", "category-ontology.json", "category_confidence", 'href="use/"'):
        require(marker in html, f"public/index.html is missing marker: {marker}")
    use_html = (root / "public/use/index.html").read_text(encoding="utf-8")
    require("VRChatワールドへの掲示" in use_html, "public/use/index.html is missing distribution guidance")
    require((root / "public/media/poster-square.webp").stat().st_size > 0, "poster-square.webp is empty")
    require((root / "public/media/poster-portrait.webp").stat().st_size > 0, "poster-portrait.webp is empty")

    allowed_categories = {item.get("id") for item in category_ontology.get("categories", []) if isinstance(item, dict) and item.get("id")}
    required_categories = {"community", "music", "performance", "game", "learning", "technology", "art", "world_tour", "wellness", "language_exchange", "recruitment_deadline", "other"}
    allowed_modes = {"in_world", "stream", "hybrid", "offline", "deadline", "unknown"}
    require(category_ontology.get("schema_version") == "2.0", "category ontology schema mismatch")
    require(category_ontology.get("default_category") == "other", "category ontology default must be other")
    require(required_categories <= allowed_categories, "category ontology is missing required categories")
    require(all(row.get("category") in allowed_categories for row in rows), "event contains unknown category")
    require(all(row.get("event_mode") in allowed_modes for row in rows), "event contains unknown event_mode")
    require(all(isinstance(row.get("category_confidence"), (int, float)) for row in rows), "event contains invalid category_confidence")
    require(not any(row.get("category") == "event" for row in rows), "legacy generic event category remains")

    require(ontology.get("schema_version") == "3.0", "event ontology schema mismatch")
    require(ontology.get("category_ontology_schema_version") == "2.0", "event ontology category schema mismatch")
    require(ontology.get("source_event_count") == len(rows), "event ontology source count mismatch")
    require(int(ontology.get("observed_entity_count") or 0) > 0, "event ontology contains no observed entities")
    require(bool(ontology.get("generated_at")), "event ontology has no generated_at")
    require(sum(ontology.get("category_breakdown", {}).values()) == len(rows), "event ontology category breakdown mismatch")
    require(ontology_audit.get("schema_version") == "2.0", "ontology audit schema mismatch")
    classification = ontology_audit.get("category_classification") or {}
    require(classification.get("event_count") == len(rows), "ontology audit event count mismatch")
    require(sum(classification.get("category_breakdown", {}).values()) == len(rows), "ontology audit category breakdown mismatch")

    require(external.get("schema_version") == "1.0", "external discovery health schema mismatch")
    require(external.get("status") in {"ok", "degraded", "skipped"}, f"external discovery has invalid status: {external.get('status')}")
    external_names = {source.get("name") for source in external.get("sources", []) if isinstance(source, dict)}
    require({"vrc_technology_academic_hub", "official_event_websites", "vrceve_authorized_feed"} <= external_names, "external discovery health is missing configured sources")

    source_status = {source.get("name"): source.get("status") for source in public_health.get("sources", []) if isinstance(source, dict)}
    require(source_status.get("yahoo_realtime_events") == "ok", "public health does not report Yahoo as healthy")
    for name in OPTIONAL_COLLECTION_SOURCES:
        status = source_status.get(name)
        require(status in {"ok", "degraded", "skipped"}, f"public health has invalid optional source status for {name}: {status}")

    for path, label in (("public/official-asset-audit.json", "official assets"), ("public/event-link-audit.json", "event links"), ("public/vrchat-group-asset-audit.json", "VRChat group assets")):
        require(isinstance(load_json(root, path), dict), f"{label} audit must be an object")
    if int(assets.get("counts", {}).get("official_x") or 0) == 0:
        annotation("warning", "asset coverage", "no event currently has an official X link")
    if int(assets.get("counts", {}).get("webp_image") or 0) == 0:
        annotation("warning", "asset coverage", "no event currently has a WebP image")
    if int(links.get("events_with_primary_action") or 0) == 0:
        annotation("warning", "link coverage", "no event currently has a primary action URL")
    if int(groups.get("events_with_group_url") or 0) == 0:
        annotation("warning", "group coverage", "no event currently has a VRChat group URL")


def write_summary(health: dict[str, Any]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [
        "### Collection health",
        "",
        f"Overall: **{health.get('status', 'unknown')}**",
        "",
        "| Source | Status | Events | Reason |",
        "| --- | --- | ---: | --- |",
    ]
    for source in health.get("sources", []):
        if not isinstance(source, dict):
            continue
        reason = str(source.get("reason") or "").replace("|", "\\|")
        lines.append(f"| {source.get('name', '')} | {source.get('status', '')} | {source.get('count', 0)} | {reason} |")
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    try:
        health = sync_collection_health(ROOT)
        validate_snapshot(ROOT)
        write_summary(health)
    except SnapshotValidationError as exc:
        annotation("error", "update snapshot validation", str(exc))
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"validated autonomous update snapshot: status={health.get('status')} events={health.get('event_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
