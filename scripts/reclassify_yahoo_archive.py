from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import collect_yahoo_corpus as corpus
from scripts import fetch_yahoo_realtime as implementation
from scripts import refine_yahoo_corpus as refinement
from scripts import run_yahoo_realtime as ledger

ARCHIVE_RETENTION_DAYS = 365


def temporal_status(start: datetime, now: datetime) -> str:
    return "past" if start < now else "upcoming"


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

    for original in history:
        row = dict(original)
        status_id = str(row.get("status_id") or "")
        source_created_at = refinement.twitter_snowflake_created_at(status_id)
        if source_created_at and source_created_at <= actual_now + timedelta(days=1):
            row["source_created_at"] = implementation.utc_text(source_created_at)
        else:
            source_created_at = None
        anchor = (
            source_created_at
            or implementation.parse_instant(str(row.get("first_seen_at") or ""))
            or actual_now
        )

        candidate, reason = adjusted_candidate(row)
        event = None
        if candidate is not None:
            text = str(candidate.get("text") or "")
            if refinement.giveaway_without_event_access(text):
                reason = "giveaway_only"
            else:
                parsed = implementation.parse_event_datetime(text, anchor)
                if parsed is None:
                    reason = "missing_datetime"
                elif parsed > actual_now + timedelta(days=180):
                    reason = "too_far_future_now"
                else:
                    event, reason = corpus.refined_candidate_to_event(
                        candidate,
                        now=parsed.astimezone(UTC),
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

        if event:
            row["last_decision"] = "accepted"
            row["last_reason"] = None
            accepted.append(event)
        else:
            resolved = reason or "unknown"
            row["last_decision"] = "rejected"
            row["last_reason"] = resolved
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
    corpus.configure_classifier()
    implementation.PARSER_VERSION = "1.9"
    now = datetime.now(UTC).replace(microsecond=0)
    history_payload = corpus.read_json(ledger.HISTORY_PATH, {})
    if not isinstance(history_payload, dict):
        raise ValueError("Yahoo candidate history must be an object")
    history = history_payload.get("candidates", [])
    if not isinstance(history, list):
        raise ValueError("Yahoo candidate history candidates must be an array")

    x_ids = implementation.known_x_ids(implementation.read_array(implementation.X_EVENTS_PATH))
    accepted, rejected, evaluated = reclassify(
        [row for row in history if isinstance(row, dict)],
        actual_now=now,
        x_ids=x_ids,
    )

    history_payload.update(
        {
            "schema_version": "2.4",
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
        }
    )
    implementation.write_json(implementation.HEALTH_PATH, health)
    print(
        "Yahoo archive reclassification: "
        f"history={len(evaluated)} accepted={len(accepted)} rejected={len(rejected)} "
        f"past={audit['past_accepted_count']} low_retweet={audit['low_retweet_accepted_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
