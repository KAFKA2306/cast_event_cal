from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import fetch_yahoo_realtime as implementation
from scripts import reclassify_yahoo_archive as archive

HISTORY_PATH = Path("public/yahoo-candidate-history.json")
PROMOTION_REVIEW_PATH = Path("tests/fixtures/yahoo-reviewed-non-datetime-promotions.json")
MIN_HISTORY_COUNT = 5000
MIN_PROMOTED_MISSING_DATETIME = 50


def source_status_id(event: dict[str, Any]) -> str:
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


def replay() -> dict[str, Any]:
    payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    history = [row for row in payload.get("candidates", []) if isinstance(row, dict)]
    if len(history) < MIN_HISTORY_COUNT:
        raise AssertionError(f"history too small: {len(history)} < {MIN_HISTORY_COUNT}")

    replay_now = implementation.parse_instant(str(payload.get("generated_at") or ""))
    if replay_now is None:
        raise AssertionError("history generated_at is required for deterministic replay")

    before_by_id = {str(row.get("status_id") or ""): row for row in history}
    accepted_before = {
        status_id
        for status_id, row in before_by_id.items()
        if row.get("last_decision") == "accepted"
    }
    missing_before = {
        status_id
        for status_id, row in before_by_id.items()
        if row.get("last_reason") == "missing_datetime"
    }

    archive.configure_archive_classifier()
    x_ids = implementation.known_x_ids(implementation.read_array(implementation.X_EVENTS_PATH))
    accepted, _rejected, evaluated = archive.reclassify(
        history,
        actual_now=replay_now,
        x_ids=x_ids,
    )
    accepted_by_id: dict[str, dict[str, Any]] = {}
    for event in accepted:
        status_id = source_status_id(event)
        if status_id:
            accepted_by_id.setdefault(status_id, event)
    accepted_after = set(accepted_by_id)
    accepted_with_resolution_evidence = sorted(
        status_id
        for status_id, event in accepted_by_id.items()
        if event.get("date_resolution_evidence")
        and event.get("date_resolution_method")
    )

    lost = sorted(accepted_before - accepted_after)
    promoted = sorted(accepted_after - accepted_before)
    promoted_missing = sorted(set(promoted) & missing_before)
    promoted_previous_reason_counts: dict[str, int] = {}
    for status_id in promoted:
        reason = str(before_by_id[status_id].get("last_reason") or "none")
        promoted_previous_reason_counts[reason] = (
            promoted_previous_reason_counts.get(reason, 0) + 1
        )
    promoted_without_evidence = sorted(
        status_id
        for status_id in promoted_missing
        if not accepted_by_id[status_id].get("date_resolution_evidence")
    )
    promoted_other = [
        {
            "status_id": status_id,
            "previous_reason": before_by_id[status_id].get("last_reason"),
            "starts_at": accepted_by_id[status_id].get("starts_at"),
            "date_resolution_method": accepted_by_id[status_id].get("date_resolution_method"),
            "date_resolution_evidence": accepted_by_id[status_id].get("date_resolution_evidence"),
            "text_excerpt": str(before_by_id[status_id].get("text") or "")[:240],
        }
        for status_id in promoted
        if status_id not in missing_before
    ]

    promotion_review = json.loads(PROMOTION_REVIEW_PATH.read_text(encoding="utf-8"))
    reviewed_valid = {
        str(status_id): str(reason)
        for status_id, reason in promotion_review.get("reviewed_valid_promotions", {}).items()
    }
    reviewed_false = {
        str(status_id): str(reason)
        for status_id, reason in promotion_review.get("reviewed_false_positives", {}).items()
    }
    unreviewed_other = [
        row for row in promoted_other if row["status_id"] not in reviewed_valid
    ]
    review_reason_mismatches = [
        {
            "status_id": row["status_id"],
            "expected_previous_reason": reviewed_valid.get(row["status_id"]),
            "actual_previous_reason": row["previous_reason"],
        }
        for row in promoted_other
        if row["status_id"] in reviewed_valid
        and reviewed_valid[row["status_id"]] != str(row["previous_reason"])
    ]
    reviewed_false_promoted = [
        row for row in promoted_other if row["status_id"] in reviewed_false
    ]
    promoted_other_without_evidence = [
        row["status_id"]
        for row in promoted_other
        if not row.get("date_resolution_evidence")
    ]

    method_counts: dict[str, int] = {}
    promoted_rows: list[dict[str, Any]] = []
    for status_id in promoted_missing:
        event = accepted_by_id[status_id]
        method = str(event.get("date_resolution_method") or "missing")
        method_counts[method] = method_counts.get(method, 0) + 1
        original = before_by_id[status_id]
        promoted_rows.append(
            {
                "status_id": status_id,
                "starts_at": event.get("starts_at"),
                "method": method,
                "text_excerpt": str(original.get("text") or "")[:240],
            }
        )

    blocker_counts: dict[str, int] = {}
    blocker_samples: dict[str, list[dict[str, str]]] = {}
    for row in evaluated:
        if row.get("last_reason") != "missing_datetime":
            continue
        blocker = str(row.get("resolution_blocker") or "none")
        blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
        samples = blocker_samples.setdefault(blocker, [])
        if len(samples) < 12:
            samples.append(
                {
                    "status_id": str(row.get("status_id") or ""),
                    "decision": str(row.get("publishability_decision") or ""),
                    "text_excerpt": str(row.get("text") or row.get("text_excerpt") or "")[:220],
                }
            )

    changed_existing = []
    previous_events = {
        str(row.get("status_id") or ""): row
        for row in history
        if row.get("last_decision") == "accepted"
    }
    for status_id in sorted(accepted_before & accepted_after):
        previous_start = str(previous_events[status_id].get("starts_at") or "")
        current_start = str(accepted_by_id[status_id].get("starts_at") or "")
        if previous_start and current_start and previous_start != current_start:
            changed_existing.append(
                {
                    "status_id": status_id,
                    "previous_starts_at": previous_start,
                    "current_starts_at": current_start,
                }
            )

    return {
        "schema_version": "1.0",
        "history_count": len(history),
        "replay_generated_at": implementation.utc_text(replay_now),
        "accepted_before": len(accepted_before),
        "accepted_after": len(accepted_after),
        "accepted_occurrence_count": len(accepted),
        "recurrence_occurrence_count": sum(
            str(event.get("date_resolution_method") or "").startswith("recurrence_")
            for event in accepted
        ),
        "accepted_with_resolution_evidence": len(accepted_with_resolution_evidence),
        "existing_accepted_lost": len(lost),
        "lost_status_ids": lost,
        "newly_promoted": len(promoted),
        "promoted_previous_reason_counts": dict(sorted(promoted_previous_reason_counts.items())),
        "promoted_from_other_reasons": len(promoted_other),
        "promoted_from_missing_datetime": len(promoted_missing),
        "promoted_without_resolution_evidence": len(promoted_without_evidence),
        "promoted_other_without_resolution_evidence": promoted_other_without_evidence,
        "reviewed_other_promotions": len(promoted_other) - len(unreviewed_other),
        "unreviewed_other_promotions": unreviewed_other,
        "review_reason_mismatches": review_reason_mismatches,
        "reviewed_false_promoted": reviewed_false_promoted,
        "promoted_method_counts": dict(sorted(method_counts.items())),
        "resolution_blocker_counts": dict(sorted(blocker_counts.items())),
        "resolution_blocker_samples": {
            key: blocker_samples[key] for key in sorted(blocker_samples)
        },
        "promoted_other": promoted_other,
        "changed_existing_starts_at": len(changed_existing),
        "promoted": promoted_rows,
        "evaluated_count": len(evaluated),
    }


def assert_targets(report: dict[str, Any], min_promoted: int) -> None:
    assert report["existing_accepted_lost"] == 0, report["lost_status_ids"]
    assert report["promoted_without_resolution_evidence"] == 0
    assert report["promoted_other_without_resolution_evidence"] == []
    assert report["unreviewed_other_promotions"] == []
    assert report["review_reason_mismatches"] == []
    assert report["reviewed_false_promoted"] == []
    assert report["newly_promoted"] == (
        report["promoted_from_missing_datetime"] + report["promoted_from_other_reasons"]
    )

    durable = int(report["accepted_with_resolution_evidence"])
    assert durable >= min_promoted, (durable, min_promoted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assert-targets", action="store_true")
    parser.add_argument("--min-promoted", type=int, default=MIN_PROMOTED_MISSING_DATETIME)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = replay()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")

    if args.assert_targets:
        assert_targets(report, args.min_promoted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
