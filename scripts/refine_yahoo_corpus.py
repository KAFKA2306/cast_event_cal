from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import collect_yahoo_corpus as corpus
from scripts import fetch_yahoo_realtime as implementation
from scripts import run_yahoo_realtime as ledger

TWITTER_EPOCH_MS = 1_288_834_974_657
AUDIT_PATH = Path("public/yahoo-classifier-audit.json")
STRONG_GIVEAWAY_TERMS = {
    "プレゼント企画",
    "無料配布",
    "商品をギフト",
    "商品プレゼント",
    "抽選で",
    "boothのお好きな商品",
    "ショップ新作",
}
VR_EVENT_ACCESS_TERMS = {
    "join",
    "ジョイン",
    "リクイン",
    "reqin",
    "request invite",
    "リクエストインバイト",
    "グループインスタンス",
    "group instance",
    "group+",
    "インスタンス先着",
    "入場",
    "開場",
}


def twitter_snowflake_created_at(status_id: str) -> datetime | None:
    try:
        value = int(status_id)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    milliseconds = (value >> 22) + TWITTER_EPOCH_MS
    try:
        created = datetime.fromtimestamp(milliseconds / 1000, tz=UTC)
    except (OSError, OverflowError, ValueError):
        return None
    if created.year < 2006:
        return None
    return created


def rejection_row(row: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "status_id": row.get("status_id"),
        "url": row.get("url"),
        "reason": reason,
        "retweet_count": row.get("retweet_count"),
        "first_seen_at": row.get("first_seen_at"),
        "last_seen_at": row.get("last_seen_at"),
        "source_created_at": row.get("source_created_at"),
        "text_excerpt": str(row.get("text") or "")[:360],
    }


def giveaway_without_event_access(text: str) -> bool:
    return (
        corpus.has_any(text, STRONG_GIVEAWAY_TERMS)
        and not corpus.has_any(text, corpus.SPECIFIC_EVENT_TERMS)
        and not corpus.has_any(text, VR_EVENT_ACCESS_TERMS)
    )


def reevaluate_with_source_time(
    history: list[dict[str, Any]],
    *,
    actual_now: datetime,
    min_retweets: int,
    x_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    evaluated: list[dict[str, Any]] = []
    for original in history:
        row = dict(original)
        status_id = str(row.get("status_id") or "")
        source_created_at = twitter_snowflake_created_at(status_id)
        if source_created_at and source_created_at <= actual_now + timedelta(days=1):
            row["source_created_at"] = implementation.utc_text(source_created_at)
        else:
            source_created_at = None
        anchor = (
            source_created_at
            or implementation.parse_instant(str(row.get("first_seen_at") or ""))
            or actual_now
        )
        candidate = {
            "status_id": status_id,
            "url": row.get("url"),
            "text": row.get("text"),
            "author": row.get("author"),
            "retweet_count": row.get("retweet_count"),
        }
        text = str(candidate.get("text") or "")
        if giveaway_without_event_access(text):
            event, reason = None, "giveaway_only"
        else:
            event, reason = corpus.refined_candidate_to_event(
                candidate,
                now=anchor,
                min_retweets=min_retweets,
                x_ids=x_ids,
            )
        if event:
            start = implementation.parse_instant(str(event.get("starts_at") or ""))
            if start is None:
                reason = "missing_datetime"
                event = None
            elif start < actual_now - timedelta(hours=12):
                reason = "past_event_now"
                event = None
            elif start > actual_now + timedelta(days=180):
                reason = "too_far_future_now"
                event = None
        if event:
            row["last_decision"] = "accepted"
            row["last_reason"] = None
            accepted.append(event)
        else:
            resolved_reason = reason or "unknown"
            row["last_decision"] = "rejected"
            row["last_reason"] = resolved_reason
            rejected.append(rejection_row(row, resolved_reason))
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


def build_audit(
    evaluated: list[dict[str, Any]],
    query_results: list[dict[str, Any]],
    target: int,
    now: datetime,
) -> dict[str, Any]:
    decisions = Counter(str(row.get("last_decision") or "unknown") for row in evaluated)
    reasons = Counter(str(row.get("last_reason") or "accepted") for row in evaluated)
    high_retweet: list[dict[str, Any]] = []
    suspicious: list[dict[str, Any]] = []
    for row in evaluated:
        retweets = int(row.get("max_retweet_count") or row.get("retweet_count") or 0)
        if row.get("last_decision") == "rejected" and retweets >= 3:
            high_retweet.append(
                {
                    "status_id": row.get("status_id"),
                    "url": row.get("url"),
                    "retweet_count": retweets,
                    "reason": row.get("last_reason"),
                    "source_created_at": row.get("source_created_at"),
                    "text_excerpt": str(row.get("text") or "")[:360],
                    "query_groups": row.get("query_groups", []),
                }
            )
        if row.get("last_decision") == "accepted" and (
            corpus.has_any(str(row.get("text") or ""), implementation.PRODUCT_TERMS)
            or corpus.has_any(str(row.get("text") or ""), implementation.GIVEAWAY_TERMS)
        ):
            suspicious.append(
                {
                    "status_id": row.get("status_id"),
                    "url": row.get("url"),
                    "source_created_at": row.get("source_created_at"),
                    "text_excerpt": str(row.get("text") or "")[:360],
                }
            )
    high_retweet.sort(key=lambda item: int(item["retweet_count"]), reverse=True)
    total = len(evaluated)
    accepted_count = decisions.get("accepted", 0)
    return {
        "schema_version": "1.2",
        "classifier_version": implementation.PARSER_VERSION,
        "generated_at": implementation.utc_text(now),
        "target_count": target,
        "candidate_count": total,
        "target_reached": total >= target,
        "accepted_count": accepted_count,
        "rejected_count": decisions.get("rejected", 0),
        "acceptance_rate": round(accepted_count / total, 6) if total else 0.0,
        "rejection_reason_counts": {
            key: value for key, value in sorted(reasons.items()) if key != "accepted"
        },
        "query_results": query_results,
        "high_retweet_rejections": high_retweet[:200],
        "suspicious_accepted_commerce": suspicious[:100],
        "quality": {
            "duplicate_status_ids": total
            - len({str(row.get("status_id")) for row in evaluated}),
            "missing_first_seen_at": sum(not row.get("first_seen_at") for row in evaluated),
            "missing_last_seen_at": sum(not row.get("last_seen_at") for row in evaluated),
            "missing_source_created_at": sum(
                not row.get("source_created_at") for row in evaluated
            ),
            "ambiguous_decisions": sum(
                row.get("last_decision") not in {"accepted", "rejected"}
                for row in evaluated
            ),
        },
    }


def main() -> int:
    corpus.configure_classifier()
    implementation.PARSER_VERSION = "1.7"
    now = datetime.now(UTC).replace(microsecond=0)
    history_payload = corpus.read_json(ledger.HISTORY_PATH, {})
    if not isinstance(history_payload, dict):
        raise ValueError("Yahoo candidate history must be an object")
    history = history_payload.get("candidates", [])
    if not isinstance(history, list):
        raise ValueError("Yahoo candidate history candidates must be an array")
    min_retweets = int(os.environ.get("YAHOO_MIN_RETWEETS", "3"))
    x_ids = implementation.known_x_ids(implementation.read_array(implementation.X_EVENTS_PATH))
    accepted, rejected, evaluated = reevaluate_with_source_time(
        [row for row in history if isinstance(row, dict)],
        actual_now=now,
        min_retweets=min_retweets,
        x_ids=x_ids,
    )
    history_payload.update(
        {
            "schema_version": "2.2",
            "generated_at": implementation.utc_text(now),
            "candidate_count": len(evaluated),
            "source_time_policy": "x_snowflake_created_at_then_first_seen_at",
            "giveaway_policy": "require_specific_event_or_vrchat_access_method",
            "candidates": evaluated,
        }
    )
    implementation.write_json(ledger.HISTORY_PATH, history_payload)
    implementation.write_json(implementation.OUTPUT_PATH, accepted)
    implementation.write_json(implementation.REJECTED_PATH, rejected[:2000])

    previous_audit = corpus.read_json(AUDIT_PATH, {})
    query_results = (
        previous_audit.get("query_results", []) if isinstance(previous_audit, dict) else []
    )
    target = int(history_payload.get("target_count") or 1000)
    audit = build_audit(evaluated, query_results, target, now)
    implementation.write_json(AUDIT_PATH, audit)

    health = ledger.read_object(implementation.HEALTH_PATH)
    health.update(
        {
            "schema_version": "2.2",
            "parser_version": implementation.PARSER_VERSION,
            "generated_at": implementation.utc_text(now),
            "event_count": len(accepted),
            "history_candidate_count": len(evaluated),
            "history_accepted_count": len(accepted),
            "history_rejected_count": len(rejected),
            "source_timestamp_count": sum(
                bool(row.get("source_created_at")) for row in evaluated
            ),
            "source_time_policy": history_payload["source_time_policy"],
            "giveaway_policy": history_payload["giveaway_policy"],
            "rejection_counts": audit["rejection_reason_counts"],
        }
    )
    implementation.write_json(implementation.HEALTH_PATH, health)
    print(
        "Yahoo corpus refinement: "
        f"history={len(evaluated)} accepted={len(accepted)} rejected={len(rejected)} "
        f"source_timestamps={health['source_timestamp_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
