from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import audit_yahoo_datetime_vocabulary as datetime_audit
from scripts import collect_yahoo_corpus as corpus
from scripts import fetch_yahoo_realtime as implementation
from scripts import refine_yahoo_corpus as refinement
from scripts import run_yahoo_realtime as ledger
from scripts.yahoo_evidence_graph import (
    build_evidence_graph,
    event_fingerprints,
    resolve_corroborated_datetime,
)
from scripts.relative_datetime import (
    EXPLICIT_DATE_PATTERN,
    install_classifier_datetime,
    resolve_recurring_event,
)

ARCHIVE_RETENTION_DAYS = 365
PUBLISHABILITY_AUDIT_PATH = Path("public/yahoo-publishability-audit.json")


def configure_archive_classifier() -> None:
    corpus.configure_classifier()
    install_classifier_datetime(corpus, implementation)
    implementation.PARSER_VERSION = "2.0"


def temporal_status(start: datetime, now: datetime) -> str:
    return "past" if start < now else "upcoming"


def source_anchor(row: dict[str, Any], actual_now: datetime) -> datetime:
    status_id = str(row.get("status_id") or "")
    created_at = refinement.twitter_snowflake_created_at(status_id)
    if created_at and created_at <= actual_now + timedelta(days=1):
        return created_at
    return (
        implementation.parse_instant(str(row.get("first_seen_at") or ""))
        or actual_now
    )


def adjusted_candidate(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    candidate = {
        "status_id": str(row.get("status_id") or ""),
        "url": row.get("url"),
        "text": row.get("text"),
        "author": row.get("author"),
        "retweet_count": row.get("retweet_count"),
    }
    value = candidate.get("retweet_count")
    if value is None:
        return None, "retweet_count_missing"
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None, "retweet_count_invalid"
    if count < 0:
        return None, "retweet_count_invalid"
    candidate["retweet_count"] = max(count, 3)
    return candidate, None


def reclassify(
    history: list[dict[str, Any]],
    *,
    actual_now: datetime,
    x_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    evaluated: list[dict[str, Any]] = []
    evidence_graph = build_evidence_graph(
        history,
        anchor_for=lambda row: source_anchor(row, actual_now),
    )

    for original in history:
        row = dict(original)
        status_id = str(row.get("status_id") or "")
        anchor = source_anchor(row, actual_now)
        source_created_at = refinement.twitter_snowflake_created_at(status_id)
        if source_created_at and source_created_at <= actual_now + timedelta(days=1):
            row["source_created_at"] = implementation.utc_text(source_created_at)

        candidate, reason = adjusted_candidate(row)
        event = None
        if candidate is not None:
            text = str(candidate.get("text") or "")
            if refinement.giveaway_without_event_access(text):
                reason = "giveaway_only"
            else:
                parsed = implementation.parse_event_datetime(text, anchor)
                if parsed is None:
                    recurrence = resolve_recurring_event(
                        text,
                        anchor,
                        materialize_after=actual_now,
                    )
                    if recurrence is None:
                        corroborated = resolve_corroborated_datetime(
                            row,
                            graph=evidence_graph,
                            anchor=anchor,
                            actual_now=actual_now,
                        )
                        if corroborated is None:
                            reason = "missing_datetime"
                        else:
                            event, reason = corpus.refined_candidate_to_event_at(
                                candidate,
                                event_at=corroborated.event_at,
                                now=actual_now,
                                min_retweets=3,
                                x_ids=x_ids,
                            )
                            if event:
                                evidence = corroborated.evidence(implementation.utc_text)
                                event["date_resolution_method"] = evidence["method"]
                                event["date_resolution_anchor"] = evidence["anchor"]
                                event["date_resolution_evidence"] = evidence
                                event["event_fingerprint"] = corroborated.event_fingerprint
                                event["corroborating_source_ids"] = list(
                                    corroborated.corroborating_source_ids
                                )
                    else:
                        event, reason = corpus.refined_candidate_to_event_at(
                            candidate,
                            event_at=recurrence.event_at,
                            now=actual_now,
                            min_retweets=3,
                            x_ids=x_ids,
                        )
                        if event:
                            evidence = recurrence.evidence(implementation.utc_text)
                            event["date_resolution_method"] = evidence["method"]
                            event["date_resolution_anchor"] = evidence["anchor"]
                            event["date_resolution_evidence"] = evidence
                            event["recurrence_rule"] = recurrence.recurrence_rule
                elif parsed > actual_now + timedelta(days=180):
                    reason = "too_far_future_now"
                else:
                    classification_anchor = (
                        parsed.astimezone(UTC)
                        if EXPLICIT_DATE_PATTERN.search(text)
                        else anchor
                    )
                    event, reason = corpus.refined_candidate_to_event(
                        candidate,
                        now=classification_anchor,
                        min_retweets=3,
                        x_ids=x_ids,
                    )

        if event:
            start = implementation.parse_instant(str(event.get("starts_at") or ""))
            if start is None:
                event = None
                reason = "missing_datetime"
            else:
                observed = int(row.get("retweet_count") or 0)
                event["retweet_count"] = observed
                event["temporal_status"] = temporal_status(start, actual_now)
                event["is_archived"] = start < actual_now
                tags = [
                    tag
                    for tag in event.get("tags", [])
                    if tag != "リポスト3件以上"
                ]
                tags.append("終了済み" if start < actual_now else "開催予定")
                tags.append(f"リポスト{observed}件")
                event["tags"] = tags

        row["resolver_version"] = implementation.PARSER_VERSION
        row["event_fingerprints"] = sorted(event_fingerprints(row))
        if event:
            row["last_decision"] = "accepted"
            row["last_reason"] = None
            row["publishability_state"] = "publishable"
            row["publishability_decision"] = "accepted_event"
            row["date_resolution_method"] = event.get("date_resolution_method")
            evidence = event.get("date_resolution_evidence")
            if evidence:
                row["date_resolution_evidence"] = evidence
            accepted.append(event)
        else:
            resolved = reason or "unknown"
            row["last_decision"] = "rejected"
            row["last_reason"] = resolved
            if resolved == "missing_datetime":
                text = str(row.get("text") or row.get("text_excerpt") or "")
                occurrence = datetime_audit.occurrence_decision(text)
                row["publishability_decision"] = occurrence
                row["publishability_state"] = datetime_audit.publishability_state(occurrence)
            else:
                row["publishability_decision"] = resolved
                if resolved in {
                    "missing_event_marker",
                    "product_only",
                    "giveaway_only",
                    "not_vrchat",
                }:
                    row["publishability_state"] = "confirmed_non_event"
                elif resolved in {"past_event", "past_event_now"}:
                    row["publishability_state"] = "past_only"
                else:
                    row["publishability_state"] = "policy_rejected"
            rejected.append(refinement.rejection_row(row, resolved))
        evaluated.append(row)

    accepted.sort(key=lambda item: (str(item.get("starts_at")), str(item.get("source_id"))))
    rejected.sort(
        key=lambda item: (
            -int(item.get("retweet_count") or 0),
            str(item.get("reason")),
            str(item.get("status_id")),
        )
    )
    return accepted, rejected, evaluated


def main() -> int:
    configure_archive_classifier()
    now = datetime.now(UTC).replace(microsecond=0)
    history_payload = corpus.read_json(ledger.HISTORY_PATH, {})
    if not isinstance(history_payload, dict):
        raise ValueError("Yahoo candidate history must be an object")
    history = history_payload.get("candidates", [])
    if not isinstance(history, list):
        raise ValueError("Yahoo candidate history candidates must be an array")

    input_rows = [row for row in history if isinstance(row, dict)]
    before_publishability = datetime_audit.build(input_rows)
    previous_missing_ids = {
        str(row.get("status_id") or "")
        for row in input_rows
        if row.get("last_reason") == "missing_datetime"
    }

    x_ids = implementation.known_x_ids(implementation.read_array(implementation.X_EVENTS_PATH))
    accepted, rejected, evaluated = reclassify(
        input_rows,
        actual_now=now,
        x_ids=x_ids,
    )

    history_payload.update(
        {
            "schema_version": "2.5",
            "generated_at": implementation.utc_text(now),
            "candidate_count": len(evaluated),
            "source_time_policy": "x_snowflake_created_at_then_first_seen_at",
            "engagement_policy": "retweet_count_required_but_no_minimum",
            "temporal_policy": f"retain_past_events_for_{ARCHIVE_RETENTION_DAYS}_day_candidate_history",
            "giveaway_policy": "require_specific_event_or_vrchat_access_method",
            "candidates": evaluated,
        }
    )
    implementation.write_json(ledger.HISTORY_PATH, history_payload)
    implementation.write_json(implementation.OUTPUT_PATH, accepted)
    implementation.write_json(implementation.REJECTED_PATH, rejected)

    accepted_by_status = {
        str(event.get("source_id") or "").rsplit(":", 1)[-1]: event
        for event in accepted
        if event.get("source_id")
    }
    promoted_from_missing = sorted(previous_missing_ids & set(accepted_by_status))
    recurrence_materialized = [
        event
        for event in accepted
        if str(event.get("date_resolution_method") or "").startswith("recurrence_")
    ]
    resolution_method_counts: dict[str, int] = {}
    for event in accepted:
        method = str(event.get("date_resolution_method") or "missing")
        resolution_method_counts[method] = resolution_method_counts.get(method, 0) + 1
    decision_counts = before_publishability.get("occurrence_decision_counts", {})
    publishability_backlog = sum(
        int(decision_counts.get(name, 0))
        for name in ("recurring_event", "partial_datetime", "ambiguous_datetime")
    )
    publishability_report = {
        "schema_version": "1.0",
        "policy_version": "issue-196-generic-publishability.v1",
        "generated_at": implementation.utc_text(now),
        "candidate_count": len(input_rows),
        "missing_datetime_before": len(previous_missing_ids),
        "publishability_backlog_before": publishability_backlog,
        "occurrence_decision_counts_before": decision_counts,
        "accepted_event_count": len(accepted),
        "promoted_from_missing_datetime": len(promoted_from_missing),
        "promoted_status_ids": promoted_from_missing,
        "recurrence_materialized_count": len(recurrence_materialized),
        "corroborated_materialized_count": sum(
            event.get("date_resolution_method")
            == "corroborated_event_fingerprint_date_clock"
            for event in accepted
        ),
        "resolution_method_counts": dict(sorted(resolution_method_counts.items())),
        "promotions_without_provenance": sum(
            not bool(accepted_by_status[status_id].get("date_resolution_evidence"))
            for status_id in promoted_from_missing
        ),
        "resolver_version": implementation.PARSER_VERSION,
        "resolver_policy": "generic_rules_only_no_status_id_or_event_name_exceptions",
    }
    implementation.write_json(PUBLISHABILITY_AUDIT_PATH, publishability_report)

    vocabulary = refinement.build_positive_vocabulary(accepted, now)
    vocabulary.update(
        {
            "minimum_retweets": 0,
            "engagement_policy": "retweet_count_required_but_no_minimum",
        }
    )
    implementation.write_json(refinement.POSITIVE_VOCABULARY_PATH, vocabulary)

    previous_audit = corpus.read_json(refinement.AUDIT_PATH, {})
    query_results = previous_audit.get("query_results", []) if isinstance(previous_audit, dict) else []
    target = int(history_payload.get("target_count") or 1000)
    audit = refinement.build_audit(evaluated, query_results, target, now)
    audit.update(
        {
            "classifier_version": implementation.PARSER_VERSION,
            "schema_version": "1.4",
            "engagement_policy": "retweet_count_required_but_no_minimum",
            "temporal_policy": "past_events_are_accepted_and_marked_archived",
            "past_accepted_count": sum(bool(row.get("is_archived")) for row in accepted),
            "low_retweet_accepted_count": sum(int(row.get("retweet_count") or 0) < 3 for row in accepted),
        }
    )
    implementation.write_json(refinement.AUDIT_PATH, audit)

    health = ledger.read_object(implementation.HEALTH_PATH)
    health.update(
        {
            "schema_version": "2.3",
            "parser_version": implementation.PARSER_VERSION,
            "generated_at": implementation.utc_text(now),
            "event_count": len(accepted),
            "history_candidate_count": len(evaluated),
            "history_accepted_count": len(accepted),
            "history_rejected_count": len(rejected),
            "source_timestamp_count": sum(bool(row.get("source_created_at")) for row in evaluated),
            "engagement_policy": history_payload["engagement_policy"],
            "temporal_policy": history_payload["temporal_policy"],
            "rejection_counts": audit["rejection_reason_counts"],
            "publishability_backlog_before": publishability_report["publishability_backlog_before"],
            "promoted_from_missing_datetime": publishability_report["promoted_from_missing_datetime"],
            "recurrence_materialized_count": publishability_report["recurrence_materialized_count"],
            "corroborated_materialized_count": publishability_report["corroborated_materialized_count"],
            "promotions_without_provenance": publishability_report["promotions_without_provenance"],
        }
    )
    implementation.write_json(implementation.HEALTH_PATH, health)
    print(
        "Yahoo archive reclassification: "
        f"history={len(evaluated)} accepted={len(accepted)} rejected={len(rejected)} "
        f"past={audit['past_accepted_count']} low_retweet={audit['low_retweet_accepted_count']} "
        f"promoted_missing={publishability_report['promoted_from_missing_datetime']} "
        f"recurrence={publishability_report['recurrence_materialized_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
