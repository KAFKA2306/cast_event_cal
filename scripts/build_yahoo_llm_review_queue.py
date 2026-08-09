from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HISTORY_PATH = Path("public/yahoo-candidate-history.json")
CLASSIFIER_AUDIT_PATH = Path("public/yahoo-classifier-audit.json")
QUEUE_PATH = Path("data/yahoo_llm_review_queue.json")
RESOLUTIONS_PATH = Path("data/yahoo_llm_review_resolutions.json")
AUDIT_PATH = Path("public/yahoo-llm-review-queue-audit.json")

ALWAYS_REVIEW_REASONS = {
    "conflicting_date_context",
    "missing_participation_method",
    "unknown",
    "retweet_count_missing",
    "retweet_count_invalid",
}
CONDITIONAL_REVIEW_REASONS = {
    "missing_datetime",
    "missing_event_marker",
}


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def utc_text(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def effective_retweets(row: dict[str, Any]) -> int:
    value = row.get("max_retweet_count")
    if value is None:
        value = row.get("retweet_count")
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def needs_review(row: dict[str, Any]) -> bool:
    reason = str(row.get("last_reason") or "")
    if reason in ALWAYS_REVIEW_REASONS:
        return True
    if reason in CONDITIONAL_REVIEW_REASONS:
        return effective_retweets(row) >= 3
    return False


def priority_for(row: dict[str, Any], *, accepted_suspicious: bool = False) -> str:
    if accepted_suspicious:
        return "high"
    reason = str(row.get("last_reason") or "")
    if reason in ALWAYS_REVIEW_REASONS or effective_retweets(row) >= 10:
        return "high"
    if effective_retweets(row) >= 5:
        return "medium"
    return "normal"


def resolution_ids(payload: dict[str, Any]) -> set[str]:
    rows = payload.get("resolutions", []) if isinstance(payload, dict) else []
    return {
        str(row.get("status_id"))
        for row in rows
        if isinstance(row, dict) and row.get("status_id")
    }


def previous_queue_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("items", []) if isinstance(payload, dict) else []
    return {
        str(row.get("status_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("status_id")
    }


def make_item(
    row: dict[str, Any],
    *,
    now: datetime,
    previous: dict[str, Any] | None,
    review_kind: str,
    machine_decision: str,
    machine_reason: str | None,
    accepted_suspicious: bool = False,
) -> dict[str, Any]:
    status_id = str(row.get("status_id") or "")
    queued_at = utc_text(now)
    first_queued_at = (
        str(previous.get("first_queued_at"))
        if previous and previous.get("first_queued_at")
        else queued_at
    )
    return {
        "status_id": status_id,
        "url": row.get("url"),
        "author": row.get("author"),
        "review_kind": review_kind,
        "priority": priority_for(row, accepted_suspicious=accepted_suspicious),
        "machine_decision": machine_decision,
        "machine_reason": machine_reason,
        "retweet_count": effective_retweets(row),
        "source_created_at": row.get("source_created_at"),
        "first_seen_at": row.get("first_seen_at"),
        "last_seen_at": row.get("last_seen_at"),
        "first_queued_at": first_queued_at,
        "last_queued_at": queued_at,
        "query_keys": row.get("query_keys", []),
        "query_groups": row.get("query_groups", []),
        "text_excerpt": str(row.get("text") or row.get("text_excerpt") or "")[:1000],
        "requested_llm_output": {
            "decision": "accept | reject | needs_more_evidence",
            "normalized_starts_at": "ISO-8601 UTC or null",
            "reason": "short evidence-grounded rationale",
            "rule_candidate": "deterministic rule suggestion or null",
        },
    }


def build_queue(
    history: list[dict[str, Any]],
    suspicious_accepted: list[dict[str, Any]],
    *,
    resolved_ids: set[str],
    previous_items: dict[str, dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:
    pending: dict[str, dict[str, Any]] = {}

    for row in history:
        if not isinstance(row, dict) or not row.get("status_id"):
            continue
        status_id = str(row["status_id"])
        if status_id in resolved_ids or not needs_review(row):
            continue
        pending[status_id] = make_item(
            row,
            now=now,
            previous=previous_items.get(status_id),
            review_kind="ambiguous_rejection",
            machine_decision=str(row.get("last_decision") or "rejected"),
            machine_reason=str(row.get("last_reason") or "unknown"),
        )

    for row in suspicious_accepted:
        if not isinstance(row, dict) or not row.get("status_id"):
            continue
        status_id = str(row["status_id"])
        if status_id in resolved_ids:
            continue
        source = next(
            (
                candidate
                for candidate in history
                if isinstance(candidate, dict)
                and str(candidate.get("status_id") or "") == status_id
            ),
            row,
        )
        pending[status_id] = make_item(
            source,
            now=now,
            previous=previous_items.get(status_id),
            review_kind="possible_false_positive",
            machine_decision="accepted",
            machine_reason="suspicious_accepted_commerce",
            accepted_suspicious=True,
        )

    priority_order = {"high": 0, "medium": 1, "normal": 2}
    return sorted(
        pending.values(),
        key=lambda item: (
            priority_order.get(str(item.get("priority")), 9),
            -int(item.get("retweet_count") or 0),
            str(item.get("status_id")),
        ),
    )


def main() -> int:
    now = datetime.now(UTC).replace(microsecond=0)
    history_payload = read_json(HISTORY_PATH, {})
    classifier = read_json(CLASSIFIER_AUDIT_PATH, {})
    resolutions = read_json(
        RESOLUTIONS_PATH,
        {"schema_version": "1.0", "resolutions": []},
    )
    previous_queue = read_json(QUEUE_PATH, {})

    history = history_payload.get("candidates", []) if isinstance(history_payload, dict) else []
    suspicious = (
        classifier.get("suspicious_accepted_commerce", [])
        if isinstance(classifier, dict)
        else []
    )
    if not isinstance(history, list):
        raise ValueError("Yahoo candidate history candidates must be an array")
    if not isinstance(suspicious, list):
        suspicious = []

    resolved = resolution_ids(resolutions)
    previous = previous_queue_index(previous_queue)
    items = build_queue(
        [row for row in history if isinstance(row, dict)],
        [row for row in suspicious if isinstance(row, dict)],
        resolved_ids=resolved,
        previous_items=previous,
        now=now,
    )

    queue_payload = {
        "schema_version": "1.0",
        "generated_at": utc_text(now),
        "policy": {
            "purpose": "defer non-deterministic Yahoo event decisions to batched LLM review",
            "always_review_reasons": sorted(ALWAYS_REVIEW_REASONS),
            "conditional_review_reasons": sorted(CONDITIONAL_REVIEW_REASONS),
            "conditional_min_retweets": 3,
            "resolved_items_are_excluded": True,
        },
        "pending_count": len(items),
        "items": items,
    }
    write_json(QUEUE_PATH, queue_payload)

    audit = {
        "schema_version": "1.0",
        "generated_at": utc_text(now),
        "candidate_count": len(history),
        "pending_count": len(items),
        "resolved_count": len(resolved),
        "high_priority_count": sum(item["priority"] == "high" for item in items),
        "possible_false_positive_count": sum(
            item["review_kind"] == "possible_false_positive" for item in items
        ),
        "ambiguous_rejection_count": sum(
            item["review_kind"] == "ambiguous_rejection" for item in items
        ),
        "duplicate_status_ids": len(items)
        - len({str(item.get("status_id")) for item in items}),
        "status": "ok",
    }
    write_json(AUDIT_PATH, audit)
    print(
        "Yahoo LLM review queue: "
        f"pending={audit['pending_count']} high={audit['high_priority_count']} "
        f"resolved={audit['resolved_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
