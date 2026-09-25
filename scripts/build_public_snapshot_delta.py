from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

POLICY_VERSION = "public-snapshot-delta.v1"
DATETIME_REJECTION_REASONS = {"missing_datetime", "partial_datetime", "ambiguous_datetime"}
PRESENTATION_FIELDS = (
    "title",
    "description",
    "image_url",
    "preferred_image_url",
    "preferred_image_kind",
    "tags",
)
MATERIAL_FIELDS = (
    "starts_at",
    "ends_at",
    "organizer",
    "location",
    "category",
    "event_mode",
    "status",
    "source",
    "source_id",
    "url",
    "primary_action_url",
    "primary_action_kind",
    "official_website_url",
    "official_x_url",
    "vrchat_group_url",
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _parse_instant(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _identity(row: dict[str, Any]) -> str:
    value = str(row.get("occurrence_id") or row.get("id") or "").strip()
    if not value:
        raise ValueError("event lacks stable occurrence identity")
    return value


def _events_document(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    rows = payload.get("events")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{path} must contain an events array")
    if payload.get("count") != len(rows):
        raise ValueError(
            f"{path} count mismatch: count={payload.get('count')!r} actual={len(rows)}"
        )
    identities = [_identity(row) for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError(f"{path} contains duplicate occurrence identities")
    return payload, rows


def _value(row: dict[str, Any], field: str) -> Any:
    value = row.get(field)
    if field == "tags" and isinstance(value, list):
        return sorted(str(item) for item in value)
    return value


def _semantic_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "occurrence_id": _identity(row),
        **{field: _value(row, field) for field in MATERIAL_FIELDS},
        **{field: _value(row, field) for field in PRESENTATION_FIELDS},
    }


def _semantic_sha(rows: list[dict[str, Any]]) -> str:
    semantic = sorted(
        (_semantic_event(row) for row in rows),
        key=lambda row: row["occurrence_id"],
    )
    return hashlib.sha256(_canonical_json(semantic)).hexdigest()


def _snapshot(
    path: Path,
    payload: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "event_count": len(rows),
        "generated_at": payload.get("generated_at"),
        "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "semantic_sha256": _semantic_sha(rows),
    }


def _source_evidence(row: dict[str, Any]) -> tuple[set[str], set[str]]:
    source_ids: set[str] = set()
    source_record_ids: set[str] = set()
    if row.get("source_id"):
        source_ids.add(str(row["source_id"]))
    if row.get("source_record_id"):
        source_record_ids.add(str(row["source_record_id"]))
    for item in row.get("provenance") or []:
        if not isinstance(item, dict):
            continue
        if item.get("source_id"):
            source_ids.add(str(item["source_id"]))
        if item.get("source_record_id"):
            source_record_ids.add(str(item["source_record_id"]))
    return source_ids, source_record_ids


def _source_indexes(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    by_source_id: dict[str, set[str]] = {}
    by_source_record_id: dict[str, set[str]] = {}
    for row in rows:
        occurrence_id = _identity(row)
        source_ids, source_record_ids = _source_evidence(row)
        for value in source_ids:
            by_source_id.setdefault(value, set()).add(occurrence_id)
        for value in source_record_ids:
            by_source_record_id.setdefault(value, set()).add(occurrence_id)
    return by_source_id, by_source_record_id


def _recurring_series_ids(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    rows = _json(path)
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain an array")
    return {
        str(row.get("series_id"))
        for row in rows
        if isinstance(row, dict) and row.get("series_id")
    }


def _previous_datetime_rejections(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    payload = _json(path)
    rows = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain a candidates array")
    return {
        str(row.get("status_id"))
        for row in rows
        if isinstance(row, dict)
        and row.get("status_id")
        and row.get("last_decision") == "rejected"
        and str(row.get("last_reason") or "") in DATETIME_REJECTION_REASONS
    }


def _is_recurring_source(source_id: str, recurring_series_ids: set[str]) -> bool:
    return any(
        source_id.startswith(f"{series_id}:")
        for series_id in recurring_series_ids
    )


def _yahoo_status_id(source_id: str) -> str | None:
    if source_id.startswith("yahoo:x:"):
        return source_id.rsplit(":", 1)[-1]
    return None


def _health_context(path: Path | None) -> tuple[bool, list[str]]:
    if path is None or not path.exists():
        return False, ["health_artifact_missing"]
    payload = _json(path)
    sources = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(sources, list):
        return False, ["health_sources_missing"]
    degraded = sorted(
        str(row.get("name") or "unknown")
        for row in sources
        if isinstance(row, dict) and str(row.get("status") or "") != "ok"
    )
    return True, degraded


def _field_changes(
    before: dict[str, Any],
    after: dict[str, Any],
    fields: tuple[str, ...],
) -> list[str]:
    return [
        field
        for field in fields
        if _value(before, field) != _value(after, field)
    ]


def _added_reason(
    row: dict[str, Any],
    *,
    recurring_series_ids: set[str],
    previous_datetime_rejections: set[str],
    before_source_ids: dict[str, set[str]],
    before_source_record_ids: dict[str, set[str]],
) -> tuple[str, dict[str, Any]]:
    source_ids, source_record_ids = _source_evidence(row)
    previous_occurrences = sorted(
        {
            occurrence_id
            for source_id in source_ids
            for occurrence_id in before_source_ids.get(source_id, set())
        }
        | {
            occurrence_id
            for source_record_id in source_record_ids
            for occurrence_id in before_source_record_ids.get(
                source_record_id,
                set(),
            )
        }
    )
    if previous_occurrences:
        return "other", {"previous_occurrence_ids": previous_occurrences}

    if any(
        (_yahoo_status_id(source_id) or "") in previous_datetime_rejections
        for source_id in source_ids
    ):
        return "promoted_datetime_resolution", {}

    if any(
        _is_recurring_source(source_id, recurring_series_ids)
        for source_id in source_ids
    ):
        return "recurrence_materialized", {}

    return "new_discovery", {}


def _removed_reason(
    row: dict[str, Any],
    *,
    after_source_ids: dict[str, set[str]],
    after_source_record_ids: dict[str, set[str]],
    lower_bound: datetime | None,
    degraded_sources: set[str],
) -> tuple[str, dict[str, Any]]:
    source_ids, source_record_ids = _source_evidence(row)
    survivors = sorted(
        {
            occurrence_id
            for source_id in source_ids
            for occurrence_id in after_source_ids.get(source_id, set())
        }
        | {
            occurrence_id
            for source_record_id in source_record_ids
            for occurrence_id in after_source_record_ids.get(
                source_record_id,
                set(),
            )
        }
    )
    if survivors:
        return "dedup_merged", {"canonical_survivor_ids": survivors}

    source = str(row.get("source") or "")
    if source and source in degraded_sources:
        return "unknown", {"note": "source_context_not_healthy"}

    if str(row.get("status") or "").lower() in {
        "cancelled",
        "withdrawn",
        "invalid",
    }:
        return "invalidated", {}

    start = _parse_instant(row.get("starts_at"))
    end = _parse_instant(row.get("ends_at"))
    if (
        lower_bound is not None
        and (end or start) is not None
        and (end or start) < lower_bound
    ):
        return "expired", {}

    return "unknown", {}


def build_delta(
    before_path: Path,
    after_path: Path,
    *,
    health_path: Path | None = None,
    recurring_path: Path | None = None,
    previous_yahoo_history_path: Path | None = None,
    base_sha: str = "",
    past_days: int = 1,
) -> dict[str, Any]:
    before_payload, before_rows = _events_document(before_path)
    after_payload, after_rows = _events_document(after_path)
    before_by_id = {_identity(row): row for row in before_rows}
    after_by_id = {_identity(row): row for row in after_rows}

    before_ids = set(before_by_id)
    after_ids = set(after_by_id)
    added_ids = sorted(after_ids - before_ids)
    removed_ids = sorted(before_ids - after_ids)
    common_ids = sorted(before_ids & after_ids)

    health_available, degraded = _health_context(health_path)
    degraded_sources = set(degraded)
    recurring_series_ids = _recurring_series_ids(recurring_path)
    previous_datetime_rejections = _previous_datetime_rejections(
        previous_yahoo_history_path
    )
    before_source_ids, before_source_record_ids = _source_indexes(before_rows)
    after_source_ids, after_source_record_ids = _source_indexes(after_rows)

    after_generated_at = _parse_instant(after_payload.get("generated_at"))
    lower_bound = (
        after_generated_at - timedelta(days=past_days)
        if after_generated_at is not None
        else None
    )

    added: list[dict[str, Any]] = []
    for occurrence_id in added_ids:
        row = after_by_id[occurrence_id]
        reason, detail = _added_reason(
            row,
            recurring_series_ids=recurring_series_ids,
            previous_datetime_rejections=previous_datetime_rejections,
            before_source_ids=before_source_ids,
            before_source_record_ids=before_source_record_ids,
        )
        added.append(
            {
                "occurrence_id": occurrence_id,
                "reason": reason,
                "title": row.get("title"),
                **detail,
            }
        )

    removed: list[dict[str, Any]] = []
    for occurrence_id in removed_ids:
        row = before_by_id[occurrence_id]
        reason, detail = _removed_reason(
            row,
            after_source_ids=after_source_ids,
            after_source_record_ids=after_source_record_ids,
            lower_bound=lower_bound,
            degraded_sources=degraded_sources,
        )
        removed.append(
            {
                "occurrence_id": occurrence_id,
                "reason": reason,
                "title": row.get("title"),
                **detail,
            }
        )

    changed: list[dict[str, Any]] = []
    unchanged_ids: list[str] = []
    for occurrence_id in common_ids:
        before = before_by_id[occurrence_id]
        after = after_by_id[occurrence_id]
        material = _field_changes(before, after, MATERIAL_FIELDS)
        presentation = _field_changes(before, after, PRESENTATION_FIELDS)
        if material or presentation:
            kind = "material" if material else "presentation"
            if material and presentation:
                kind = "material_and_presentation"
            changed.append(
                {
                    "occurrence_id": occurrence_id,
                    "change_kind": kind,
                    "material_fields": material,
                    "presentation_fields": presentation,
                }
            )
        else:
            unchanged_ids.append(occurrence_id)

    conservation_ok = (
        len(before_rows) + len(added) - len(removed) == len(after_rows)
    )
    partition_ok = (
        len(added) + len(removed) + len(changed) + len(unchanged_ids)
        == len(before_rows) + len(added)
    )
    source_context_tainted = any(
        row.get("note") == "source_context_not_healthy"
        for row in removed
    )
    healthy = (
        health_available
        and not source_context_tainted
        and conservation_ok
        and partition_ok
        and after_generated_at is not None
    )
    if healthy and degraded:
        status = "ok_with_degraded_sources"
    elif healthy:
        status = "ok"
    elif not health_available or source_context_tainted:
        status = "degraded_source_context"
    else:
        status = "invalid_delta_context"

    return {
        "schema_version": "1.0",
        "policy_version": POLICY_VERSION,
        "status": status,
        "healthy": healthy,
        "generated_at": after_payload.get("generated_at"),
        "base_sha": base_sha,
        "before_snapshot": _snapshot(
            before_path,
            before_payload,
            before_rows,
        ),
        "after_snapshot": _snapshot(
            after_path,
            after_payload,
            after_rows,
        ),
        "counts": {
            "before": len(before_rows),
            "after": len(after_rows),
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(unchanged_ids),
            "net": len(after_rows) - len(before_rows),
        },
        "reason_counts": {
            "added": dict(
                sorted(
                    Counter(row["reason"] for row in added).items()
                )
            ),
            "removed": dict(
                sorted(
                    Counter(row["reason"] for row in removed).items()
                )
            ),
            "changed": dict(
                sorted(
                    Counter(row["change_kind"] for row in changed).items()
                )
            ),
        },
        "degraded_sources": degraded,
        "conservation": {
            "equation": "before + added - removed = after",
            "left": len(before_rows) + len(added) - len(removed),
            "right": len(after_rows),
            "ok": conservation_ok,
        },
        "partition_ok": partition_ok,
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged_ids": unchanged_ids,
    }


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\\n",
        encoding="utf-8",
    )


def append_history(
    report: dict[str, Any],
    history_path: Path,
) -> bool:
    if not report.get("healthy"):
        return False
    summary = {
        key: report[key]
        for key in (
            "schema_version",
            "policy_version",
            "status",
            "generated_at",
            "base_sha",
            "counts",
            "reason_counts",
        )
    }
    summary["before_snapshot"] = report["before_snapshot"]
    summary["after_snapshot"] = report["after_snapshot"]
    key = (
        str(summary.get("generated_at") or ""),
        str(summary["after_snapshot"].get("raw_sha256") or ""),
        str(summary.get("base_sha") or ""),
    )

    existing: list[dict[str, Any]] = []
    if history_path.exists():
        for line in history_path.read_text(
            encoding="utf-8"
        ).splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(
                    f"{history_path} contains a non-object row"
                )
            existing.append(row)
            row_key = (
                str(row.get("generated_at") or ""),
                str(
                    (row.get("after_snapshot") or {}).get(
                        "raw_sha256"
                    )
                    or ""
                ),
                str(row.get("base_sha") or ""),
            )
            if row_key == key:
                return False

    history_path.parent.mkdir(parents=True, exist_ok=True)
    existing.append(summary)
    temporary = history_path.with_suffix(
        history_path.suffix + ".tmp"
    )
    temporary.write_text(
        "".join(
            json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\\n"
            for row in existing
        ),
        encoding="utf-8",
    )
    temporary.replace(history_path)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Explain deterministic changes between two canonical "
            "public event snapshots."
        )
    )
    parser.add_argument(
        "--before",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--after",
        type=Path,
        default=Path("public/events.json"),
    )
    parser.add_argument(
        "--health",
        type=Path,
        default=Path("public/health.json"),
    )
    parser.add_argument(
        "--recurring",
        type=Path,
        default=Path("data/recurring_events.json"),
    )
    parser.add_argument(
        "--previous-yahoo-history",
        type=Path,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("audit/public-snapshot-delta.json"),
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=Path(
            "audit/public-snapshot-delta-history.jsonl"
        ),
    )
    parser.add_argument(
        "--base-sha",
        default=os.environ.get("GITHUB_SHA", ""),
    )
    parser.add_argument(
        "--past-days",
        type=int,
        default=1,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_delta(
        args.before,
        args.after,
        health_path=args.health,
        recurring_path=args.recurring,
        previous_yahoo_history_path=args.previous_yahoo_history,
        base_sha=args.base_sha,
        past_days=args.past_days,
    )
    write_report(report, args.output)
    appended = append_history(report, args.history)
    counts = report["counts"]
    print(
        "public snapshot delta: "
        f"status={report['status']} "
        f"before={counts['before']} "
        f"after={counts['after']} "
        f"added={counts['added']} "
        f"removed={counts['removed']} "
        f"changed={counts['changed']} "
        f"history_appended={str(appended).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
