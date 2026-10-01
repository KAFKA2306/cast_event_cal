from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cast_event_cal.recurrence import resolve_recurrence  # noqa: E402
from scripts.audit_yahoo_datetime_vocabulary import occurrence_decision  # noqa: E402

DEFAULT_INPUT = Path("public/yahoo-candidate-history.json")
DEFAULT_PUBLIC = Path("public/events.json")
DEFAULT_OUTPUT = Path("audit/recurring-replay.json")


def read_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("candidates", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("candidate history must contain a candidates array")
    return [row for row in rows if isinstance(row, dict)]


def read_public_starts(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("events", []) if isinstance(payload, dict) else []
    return {
        str(row.get("start", ""))
        for row in rows
        if isinstance(row, dict) and row.get("start")
    }


def candidate_fingerprint(row: dict[str, Any]) -> str:
    material = "\n".join(
        str(row.get(key, ""))
        for key in ("status_id", "url", "text", "author_id")
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def replay(
    candidates: list[dict[str, Any]],
    public_starts: set[str],
    *,
    now: datetime,
) -> dict[str, Any]:
    recurring_rows = [
        row
        for row in candidates
        if str(row.get("datetime_reason", "")) == "recurring_event"
    ]
    results: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    resolved_count = 0
    future_occurrences = 0
    duplicate_count = 0
    provenance_missing = 0

    for row in recurring_rows:
        text = str(row.get("text", ""))
        status_id = str(row.get("status_id", ""))
        url = str(row.get("url", ""))
        if not status_id and not url:
            provenance_missing += 1

        decision = occurrence_decision(text, now=now)
        rule = decision.get("rule")
        resolved = resolve_recurrence(text, now=now)
        starts = [str(item) for item in resolved.get("starts", [])]
        future = [start for start in starts if start >= now.isoformat()]
        duplicates = [start for start in future if start in public_starts]
        reason = str(resolved.get("reason") or decision.get("reason") or "unknown")
        reason_counts[reason] += 1
        if starts:
            resolved_count += 1
        future_occurrences += len(future)
        duplicate_count += len(duplicates)

        results.append(
            {
                "fingerprint": candidate_fingerprint(row),
                "status_id": status_id,
                "url": url,
                "rule": rule,
                "reason": reason,
                "resolved": bool(starts),
                "starts": starts,
                "future_starts": future,
                "duplicate_starts": duplicates,
            }
        )

    total = len(recurring_rows)
    return {
        "generated_at": now.isoformat(),
        "resolver_version": "recurrence-v1",
        "input_recurring_rows": total,
        "resolved_rows": resolved_count,
        "resolution_rate": (resolved_count / total) if total else 0.0,
        "materialized_future_occurrences": future_occurrences,
        "duplicate_delta": duplicate_count,
        "provenance_missing": provenance_missing,
        "reason_counts": dict(sorted(reason_counts.items())),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--require-gates", action="store_true")
    args = parser.parse_args()

    now = datetime.now(UTC)
    report = replay(
        read_candidates(args.input),
        read_public_starts(args.public),
        now=now,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False))

    if args.require_gates and report["provenance_missing"]:
        print("recurring replay gate failed: provenance_missing > 0", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
