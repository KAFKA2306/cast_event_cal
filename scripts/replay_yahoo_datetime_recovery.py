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
MIN_HISTORY_COUNT = 5000
MIN_PROMOTED_MISSING_DATETIME = 50


def source_status_id(event: dict[str, Any]) -> str:
    source_id = str(event.get("source_id") or "")
    return source_id.rsplit(":", 1)[-1] if source_id else ""


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
    accepted_by_id = {
        source_status_id(event): event
        for event in accepted
        if source_status_id(event)
    }
    accepted_after = set(accepted_by_id)

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
            "text_excerpt": str(before_by_id[status_id].get("text") or "")[:240],
        }
        for status_id in promoted
        if status_id not in missing_before
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
        "existing_accepted_lost": len(lost),
        "lost_status_ids": lost,
        "newly_promoted": len(promoted),
        "promoted_previous_reason_counts": dict(sorted(promoted_previous_reason_counts.items())),
        "promoted_from_other_reasons": len(promoted_other),
        "promoted_from_missing_datetime": len(promoted_missing),
        "promoted_without_resolution_evidence": len(promoted_without_evidence),
        "promoted_method_counts": dict(sorted(method_counts.items())),
        "promoted_other": promoted_other,
        "changed_existing_starts_at": len(changed_existing),
        "promoted": promoted_rows,
        "evaluated_count": len(evaluated),
    }


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
        assert report["existing_accepted_lost"] == 0, report["lost_status_ids"]
        assert report["promoted_without_resolution_evidence"] == 0
        assert report["promoted_from_other_reasons"] == 0, report["promoted_other"]
        assert report["newly_promoted"] == report["promoted_from_missing_datetime"]
        assert report["promoted_from_missing_datetime"] >= args.min_promoted, (
            report["promoted_from_missing_datetime"],
            args.min_promoted,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
