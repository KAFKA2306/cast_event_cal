from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts import collect_yahoo_corpus as corpus
from scripts import fetch_yahoo_realtime as implementation
from scripts import refine_yahoo_corpus as refinement
from scripts import run_yahoo_realtime as ledger
from scripts import yahoo_classifier_v19 as v19

OUTPUT_PATH = Path("public/yahoo-v19-recovery-audit.json")
TARGET_REASONS = {"missing_datetime", "missing_event_marker", "past_event_now"}


def main() -> int:
    corpus.configure_classifier()
    implementation.PARSER_VERSION = v19.PARSER_VERSION
    now = datetime.now(UTC).replace(microsecond=0)
    payload = corpus.read_json(ledger.HISTORY_PATH, {})
    history = [row for row in payload.get("candidates", []) if isinstance(row, dict)]
    baseline = {
        str(row.get("status_id")): {
            "decision": row.get("last_decision"),
            "reason": row.get("last_reason"),
        }
        for row in history
    }
    min_retweets = 3
    x_ids = implementation.known_x_ids(implementation.read_array(implementation.X_EVENTS_PATH))
    accepted, rejected, evaluated = refinement.reevaluate_with_source_time(
        history,
        actual_now=now,
        min_retweets=min_retweets,
        x_ids=x_ids,
    )
    transitions: Counter[str] = Counter()
    recovered: Counter[str] = Counter()
    accepted_ids = {
        str(event.get("source_id") or "").split(":")[-1]
        for event in accepted
    }
    examples: dict[str, list[dict[str, Any]]] = {reason: [] for reason in TARGET_REASONS}
    for row in evaluated:
        status_id = str(row.get("status_id") or "")
        old = baseline.get(status_id, {})
        old_reason = str(old.get("reason") or "accepted")
        new_reason = str(row.get("last_reason") or "accepted")
        transitions[f"{old_reason}->{new_reason}"] += 1
        if old_reason in TARGET_REASONS and status_id in accepted_ids:
            recovered[old_reason] += 1
            if len(examples[old_reason]) < 20:
                examples[old_reason].append(
                    {
                        "status_id": status_id,
                        "retweet_count": int(row.get("max_retweet_count") or row.get("retweet_count") or 0),
                        "url": row.get("url"),
                        "starts_at": next(
                            (
                                event.get("starts_at")
                                for event in accepted
                                if str(event.get("source_id") or "").endswith(status_id)
                            ),
                            None,
                        ),
                        "text_excerpt": str(row.get("text") or "")[:500],
                    }
                )

    low_repost_accepted = 0
    history_by_id = {str(row.get("status_id")): row for row in evaluated}
    for status_id in accepted_ids:
        row = history_by_id[status_id]
        reposts = int(row.get("max_retweet_count") or row.get("retweet_count") or 0)
        low_repost_accepted += reposts < min_retweets

    recap_accepted = sum(
        bool(v19.RECAP_RE.search(str(history_by_id[status_id].get("text") or "")))
        for status_id in accepted_ids
    )
    commerce_accepted = sum(
        corpus.has_any(str(history_by_id[status_id].get("text") or ""), implementation.GIVEAWAY_TERMS)
        and not corpus.has_any(str(history_by_id[status_id].get("text") or ""), corpus.SPECIFIC_EVENT_TERMS)
        for status_id in accepted_ids
    )
    baseline_accepted = sum(
        str(row.get("last_decision")) == "accepted" for row in history
    )
    result = {
        "schema_version": "1.0",
        "generated_at": implementation.utc_text(now),
        "baseline_classifier_version": "1.8",
        "classifier_version": v19.PARSER_VERSION,
        "candidate_count": len(history),
        "baseline_accepted_count": baseline_accepted,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "net_accepted_change": len(accepted) - baseline_accepted,
        "recovered_from_target_reasons": {
            reason: recovered.get(reason, 0) for reason in sorted(TARGET_REASONS)
        },
        "remaining_target_reasons": {
            reason: sum(row.get("last_reason") == reason for row in evaluated)
            for reason in sorted(TARGET_REASONS)
        },
        "decision_transitions": dict(sorted(transitions.items())),
        "quality": {
            "low_repost_accepted": low_repost_accepted,
            "recap_report_accepted": recap_accepted,
            "unstructured_giveaway_accepted": commerce_accepted,
            "duplicate_status_ids": len(history) - len({str(row.get("status_id")) for row in history}),
            "ambiguous_decisions": sum(
                row.get("last_decision") not in {"accepted", "rejected"} for row in evaluated
            ),
        },
        "examples": examples,
    }
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
