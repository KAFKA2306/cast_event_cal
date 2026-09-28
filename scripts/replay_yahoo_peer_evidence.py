from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import collect_yahoo_corpus as corpus
from scripts import fetch_yahoo_realtime as implementation
from scripts import reclassify_yahoo_archive as archive
from scripts import run_yahoo_realtime as ledger

DEFAULT_OUTPUT = Path("peer-evidence-replay.json")


def origin_status_id(event: dict[str, Any]) -> str:
    explicit = str(event.get("source_status_id") or "")
    if implementation.STATUS_ID_RE.fullmatch(explicit):
        return explicit
    source_id = str(
        event.get("recurrence_source_id")
        or event.get("source_id")
        or ""
    )
    match = implementation.STATUS_ID_RE.search(source_id)
    return match.group(0) if match else ""


def by_origin(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        status_id = origin_status_id(event)
        if status_id:
            grouped.setdefault(status_id, []).append(event)
    for values in grouped.values():
        values.sort(key=lambda row: str(row.get("starts_at") or ""))
    return grouped


def blocker_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        str(row.get("resolution_blocker") or "none")
        for row in rows
        if row.get("last_reason") == "missing_datetime"
    )
    return dict(sorted(counts.items()))


def run_replay(
    *,
    query_limit: int,
    delay_seconds: float,
    output: Path,
) -> dict[str, Any]:
    archive.configure_archive_classifier()
    now = datetime.now(UTC).replace(microsecond=0)

    history_payload = corpus.read_json(ledger.HISTORY_PATH, {})
    if not isinstance(history_payload, dict):
        raise ValueError("Yahoo candidate history must be an object")
    history = [
        row
        for row in history_payload.get("candidates", [])
        if isinstance(row, dict)
    ]
    if not history:
        raise ValueError("Yahoo candidate history is empty")

    plan = corpus.build_peer_evidence_query_plan(history, limit=max(0, query_limit))
    observed: list[dict[str, Any]] = []
    query_results: list[dict[str, Any]] = []
    raw_total = 0
    if plan:
        observed, query_results, raw_total = corpus.fetch_candidates(
            plan,
            {str(row.get("status_id") or "") for row in history},
            len(history) + 1000,
            False,
            max(0.0, delay_seconds),
        )

    previous_retention = ledger.HISTORY_RETENTION_DAYS
    try:
        ledger.HISTORY_RETENTION_DAYS = int(
            history_payload.get("retention_days")
            or corpus.HISTORY_RETENTION_DAYS
        )
        merged = ledger.merge_history(history, observed, now)
    finally:
        ledger.HISTORY_RETENTION_DAYS = previous_retention
    merged = corpus.merge_provenance(merged, history, observed, now)

    x_ids = implementation.known_x_ids(
        implementation.read_array(implementation.X_EVENTS_PATH)
    )
    external_events = implementation.read_array(archive.EXTERNAL_EVENTS_PATH)
    before_accepted, _, before_evaluated = archive.reclassify(
        history,
        actual_now=now,
        x_ids=x_ids,
        external_events=external_events,
    )
    after_accepted, _, after_evaluated = archive.reclassify(
        merged,
        actual_now=now,
        x_ids=x_ids,
        external_events=external_events,
    )

    before_by_origin = by_origin(before_accepted)
    after_by_origin = by_origin(after_accepted)
    lost = sorted(before_by_origin.keys() - after_by_origin.keys())
    promoted = sorted(after_by_origin.keys() - before_by_origin.keys())
    history_by_status = {
        str(row.get("status_id") or ""): row
        for row in history
    }
    promoted_existing_unresolved = [
        status_id
        for status_id in promoted
        if history_by_status.get(status_id, {}).get("last_reason")
        == "missing_datetime"
    ]
    promoted_unresolved_without_provenance = [
        status_id
        for status_id in promoted_existing_unresolved
        if not any(
            bool(event.get("date_resolution_evidence"))
            for event in after_by_origin.get(status_id, [])
        )
    ]

    before_blockers = blocker_counts(before_evaluated)
    after_blockers = blocker_counts(after_evaluated)
    existing_ids = set(history_by_status)
    observed_ids = {
        str(row.get("status_id") or "")
        for row in observed
        if row.get("status_id")
    }
    successful_queries = sum(
        row.get("status") == "ok"
        for row in query_results
    )

    report = {
        "schema_version": "1.0",
        "generated_at": implementation.utc_text(now),
        "mode": "read_only_peer_evidence_replay",
        "query_limit": query_limit,
        "queries_planned": len(plan),
        "queries_succeeded": successful_queries,
        "queries_failed": len(query_results) - successful_queries,
        "raw_candidates_fetched": raw_total,
        "unique_candidates_fetched": len(observed),
        "new_candidates_to_history": len(observed_ids - existing_ids),
        "history_before": len(history),
        "history_after_merge": len(merged),
        "accepted_sources_before": len(before_by_origin),
        "accepted_sources_after": len(after_by_origin),
        "promoted_sources": len(promoted),
        "promoted_source_ids": promoted,
        "promoted_existing_unresolved": len(promoted_existing_unresolved),
        "materialized_occurrences_before": len(before_accepted),
        "materialized_occurrences_after": len(after_accepted),
        "materialized_occurrence_delta": len(after_accepted) - len(before_accepted),
        "lost_existing_sources": len(lost),
        "lost_existing_source_ids": lost,
        "promoted_unresolved_without_provenance": len(
            promoted_unresolved_without_provenance
        ),
        "no_peer_evidence_before": int(before_blockers.get("no_peer_evidence", 0)),
        "no_peer_evidence_after": int(after_blockers.get("no_peer_evidence", 0)),
        "resolution_blockers_before": before_blockers,
        "resolution_blockers_after": after_blockers,
        "query_plan": [
            {
                "key": row["key"],
                "term": row["term"],
                "query": row["query"],
            }
            for row in plan
        ],
        "query_results": query_results,
    }
    implementation.write_json(output, report)

    print(
        "Yahoo peer evidence replay: "
        f"queries={len(plan)} ok={successful_queries} "
        f"fetched={len(observed)} new={len(observed_ids - existing_ids)} "
        f"accepted_sources={len(before_by_origin)}->{len(after_by_origin)} "
        f"occurrences={len(before_accepted)}->{len(after_accepted)} "
        f"no_peer={before_blockers.get('no_peer_evidence', 0)}"
        f"->{after_blockers.get('no_peer_evidence', 0)} "
        f"lost={len(lost)}"
    )

    if lost:
        raise SystemExit(
            f"peer evidence replay lost existing accepted sources: {lost[:10]}"
        )
    if promoted_unresolved_without_provenance:
        raise SystemExit(
            "peer evidence replay promoted unresolved rows without provenance: "
            f"{promoted_unresolved_without_provenance[:10]}"
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch targeted Yahoo peer evidence and replay resolution without publishing"
    )
    parser.add_argument("--max-queries", type=int, default=12)
    parser.add_argument("--delay-seconds", type=float, default=0.25)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run_replay(
        query_limit=max(0, args.max_queries),
        delay_seconds=max(0.0, args.delay_seconds),
        output=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
