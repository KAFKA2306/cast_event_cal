from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
JST = ZoneInfo("Asia/Tokyo")
MAX_LIMIT = 100


def _load_json(name: str) -> Any:
    return json.loads((PUBLIC / name).read_text(encoding="utf-8"))


def _events_payload() -> dict[str, Any]:
    payload = _load_json("events.json")
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise RuntimeError("public/events.json must be an object with an events array")
    return payload


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _validate_page(limit: int, offset: int) -> None:
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    if offset < 0:
        raise ValueError("offset must be non-negative")


def _series_id(row: dict[str, Any]) -> str | None:
    for key in ("ontology_id", "series_id", "canonical_series_id", "event_series_id"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def event_provenance(row: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    generated = payload.get("generated_at")
    generated_dt = _parse_time(generated)
    freshness_seconds = None
    if generated_dt is not None:
        freshness_seconds = max(0, int((datetime.now(UTC) - generated_dt.astimezone(UTC)).total_seconds()))

    tracked = {
        "source_created_at": row.get("source_created_at"),
        "first_seen_at": row.get("first_seen_at"),
        "last_seen_at": row.get("last_seen_at"),
        "ontology_id": _series_id(row),
    }
    null_reasons = {
        key: "not_recorded_in_public_event"
        for key, value in tracked.items()
        if value is None
    }
    return {
        "canonical_id": row.get("id"),
        "schema_version": payload.get("schema_version"),
        "event_start": row.get("starts_at"),
        "source_created_at": tracked["source_created_at"],
        "first_seen_at": tracked["first_seen_at"],
        "last_seen_at": tracked["last_seen_at"],
        "generated_at": generated,
        "source_type": row.get("source"),
        "source_id": row.get("source_id"),
        "source_url": row.get("url"),
        "classification_rule": row.get("category_source"),
        "classification_reason": row.get("category_evidence") or [],
        "ontology_id": tracked["ontology_id"],
        "freshness_seconds": freshness_seconds,
        "null_reasons": null_reasons,
    }


def with_provenance(row: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return {**row, "provenance": event_provenance(row, payload)}


def search_events(
    query: str | None = None,
    category: str | None = None,
    series_id: str | None = None,
    start_at: str | None = None,
    end_at: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    _validate_page(limit, offset)
    payload = _events_payload()
    rows = [row for row in payload["events"] if isinstance(row, dict)]

    if query:
        needle = query.casefold().strip()
        rows = [
            row
            for row in rows
            if needle
            in " ".join(
                str(row.get(key) or "")
                for key in ("title", "description", "organizer", "location", "source_id")
            ).casefold()
        ]
    if category:
        rows = [row for row in rows if row.get("category") == category]
    if series_id:
        rows = [row for row in rows if _series_id(row) == series_id]

    start_dt = _parse_time(start_at)
    end_dt = _parse_time(end_at)
    if start_at and start_dt is None:
        raise ValueError("start_at must be ISO-8601")
    if end_at and end_dt is None:
        raise ValueError("end_at must be ISO-8601")
    if start_dt is not None:
        rows = [row for row in rows if (dt := _parse_time(row.get("starts_at"))) is not None and dt >= start_dt]
    if end_dt is not None:
        rows = [row for row in rows if (dt := _parse_time(row.get("starts_at"))) is not None and dt < end_dt]

    total = len(rows)
    page = rows[offset : offset + limit]
    return {
        "schema_version": "cast-event.mcp-read-model.v1",
        "source_schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [with_provenance(row, payload) for row in page],
    }


def get_event(event_id: str) -> dict[str, Any] | None:
    payload = _events_payload()
    row = next((row for row in payload["events"] if isinstance(row, dict) and row.get("id") == event_id), None)
    return with_provenance(row, payload) if row is not None else None


def tonight_events(date_jst: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    _validate_page(limit, offset)
    if date_jst:
        try:
            target = date.fromisoformat(date_jst)
        except ValueError as exc:
            raise ValueError("date_jst must be YYYY-MM-DD") from exc
    else:
        target = datetime.now(JST).date()

    payload = _events_payload()
    rows = []
    for row in payload["events"]:
        if not isinstance(row, dict):
            continue
        starts = _parse_time(row.get("starts_at"))
        if starts is not None and starts.astimezone(JST).date() == target:
            rows.append(row)
    rows.sort(key=lambda row: row.get("starts_at") or "")
    total = len(rows)
    return {
        "schema_version": "cast-event.mcp-read-model.v1",
        "date_jst": target.isoformat(),
        "generated_at": payload.get("generated_at"),
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [with_provenance(row, payload) for row in rows[offset : offset + limit]],
    }


def get_series(series_id: str) -> dict[str, Any] | None:
    ontology = _load_json("event-ontology.json")
    entries = ontology.get("entries", []) if isinstance(ontology, dict) else []
    return next(
        (entry for entry in entries if isinstance(entry, dict) and entry.get("canonical_id") == series_id),
        None,
    )


def source_health() -> dict[str, Any]:
    return _load_json("health.json")


def classification_audit() -> dict[str, Any]:
    yahoo = _load_json("yahoo-classifier-audit.json")
    ontology = _load_json("ontology-match-audit.json")
    return {
        "schema_version": "cast-event.classification-audit-view.v1",
        "generated_at": yahoo.get("generated_at") if isinstance(yahoo, dict) else None,
        "yahoo_classifier": yahoo,
        "ontology_match": ontology,
    }


def ontology() -> dict[str, Any]:
    return _load_json("event-ontology.json")


def data_quality() -> dict[str, Any]:
    payload = _events_payload()
    rows = [row for row in payload["events"] if isinstance(row, dict)]
    health = source_health()
    ontology_payload = ontology()
    ids = [row.get("id") for row in rows]
    duplicate_ids = len(ids) - len(set(ids))
    ambiguous = ontology_payload.get("matching_policy", {}).get("ambiguous_match_action")
    artifacts = {}
    for name in (
        "events.json",
        "health.json",
        "event-ontology.json",
        "ontology-match-audit.json",
        "category-ontology.json",
        "yahoo-classifier-audit.json",
    ):
        path = PUBLIC / name
        raw = path.read_bytes()
        artifacts[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    return {
        "schema_version": "cast-event.data-quality.v1",
        "generated_at": payload.get("generated_at"),
        "event_count": len(rows),
        "health_event_count": health.get("event_count"),
        "event_count_matches_health": health.get("event_count") == len(rows),
        "duplicate_event_ids": duplicate_ids,
        "ontology_ambiguous_events": health.get("ontology", {}).get("ambiguous_events"),
        "ambiguous_match_action": ambiguous,
        "low_confidence_event_count": health.get("category_classification", {}).get("low_confidence_event_count"),
        "edinetdb_mode": "not_applicable",
        "canonical_repository": "KAFKA2306/cast_event_cal",
        "artifacts": artifacts,
    }


def methodology() -> dict[str, Any]:
    ontology_payload = ontology()
    health = source_health()
    return {
        "schema_version": "cast-event.methodology.v1",
        "canonical_repository": "KAFKA2306/cast_event_cal",
        "deploy_repository": "KAFKA2306/vrc_cast_event_calender",
        "classification": "deterministic_fail_close",
        "llm_as_canonical_classifier": False,
        "ontology_governance": ontology_payload.get("governance"),
        "matching_policy": ontology_payload.get("matching_policy"),
        "category_classification": health.get("category_classification"),
        "time_semantics": {
            "event_start": "starts_at",
            "source_observed": "fetched_at/source-specific observed fields when present",
            "snapshot_generated": "events.json generated_at",
            "timezone_for_tonight": "Asia/Tokyo",
        },
        "edinetdb_mode": "not_applicable",
    }
