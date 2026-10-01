from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cast_event_cal.recurrence import resolve_recurrence
from scripts.audit_yahoo_datetime_vocabulary import occurrence_decision

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
        str(row.get("starts_at"))
        for row in rows
        if isinstance(row, dict) and row.get("starts_at")
    }


def fingerprint(row: dict[str, Any]) -> str:
    payload = "|".join(
        [
            str(row.get("status_id") or ""),
            str(row.get("url") or ""),
            str(row.get("text") or row.get("text_excerpt") or ""),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def build(
    rows: list[dict[str, Any]],
    *,
    public_starts: set[str],
    after: datetime,
    count: int,
) -> dict[str, Any]:
    replay_rows: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    proposed: set[str] = set()
    duplicate_count = 0
    missing_provenance = 0
    promotions_without_provenance = 0

    for row in rows:
        text = str(row.get("text") or row.get("text_excerpt") or "")
        if occurrence_decision(text) != "recurring_event":
            continue
        evidence = {
            "status_id": str(row.get("status_id") or ""),
            "url": str(row.get("url") or ""),
            "text_excerpt": " ".join(text.split())[:500],
        }
        provenance_complete = bool(
            evidence["status_id"] and evidence["url"] and evidence["text_excerpt"]
        )
        if not provenance_complete:
            missing_provenance += 1
        resolution = resolve_recurrence(text, after=after, count=count)
        decision = str(resolution["status"])
        reason = str(resolution.get("reason") or "resolved")
        reasons[reason] += 1
        occurrences = (
            list(resolution.get("occurrences") or []) if decision == "resolved" else []
        )
        duplicates: list[str] = []
        new_occurrences: list[str] = []
        for occurrence in occurrences:
            normalized = str(occurrence).replace("+09:00", "Z")
            if normalized in public_starts or normalized in proposed:
                duplicates.append(str(occurrence))
                duplicate_count += 1
            else:
                proposed.add(normalized)
                new_occurrences.append(str(occurrence))
        if new_occurrences and not provenance_complete:
            promotions_without_provenance += len(new_occurrences)
        replay_rows.append(
            {
                "candidate_fingerprint": fingerprint(row),
                "provenance": evidence,
                "provenance_complete": provenance_complete,
                "decision": decision,
                "unresolved_reason": None if decision == "resolved" else reason,
                "rule": resolution.get("rule"),
                "resolver_version": resolution.get("resolver_version"),
                "proposed_occurrences": occurrences,
                "new_occurrences": new_occurrences,
                "duplicate_occurrences": duplicates,
            }
        )

    resolved = sum(row["decision"] == "resolved" for row in replay_rows)
    return {
        "schema_version": "1.0",
        "policy_version": "issue-313-recurring-replay.v2",
        "anchor": after.astimezone(UTC).isoformat(),
        "input_recurring_rows": len(replay_rows),
        "safely_resolved_rules": resolved,
        "resolution_rate": round(resolved / len(replay_rows), 6) if replay_rows else 0.0,
        "materialized_future_occurrences": sum(
            len(row["new_occurrences"]) for row in replay_rows
        ),
        "duplicate_delta": duplicate_count,
        "provenance_missing": missing_provenance,
        "promotions_without_provenance": promotions_without_provenance,
        "existing_accepted_loss": 0,
        "unresolved_by_reason": dict(
            sorted((key, value) for key, value in reasons.items() if key != "resolved")
        ),
        "publication_gate_passed": promotions_without_provenance == 0,
        "rows": sorted(replay_rows, key=lambda row: row["candidate_fingerprint"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only replay of recurring Yahoo candidates")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--after", help="ISO 8601 replay anchor; defaults to current UTC time")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--require-gates", action="store_true")
    args = parser.parse_args()
    if args.count < 1:
        raise SystemExit("--count must be >= 1")
    after = (
        datetime.fromisoformat(args.after.replace("Z", "+00:00"))
        if args.after
        else datetime.now(UTC).replace(microsecond=0)
    )
    if after.tzinfo is None:
        after = after.replace(tzinfo=UTC)
    payload = build(
        read_candidates(args.input),
        public_starts=read_public_starts(args.public),
        after=after,
        count=args.count,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: payload[key]
                for key in (
                    "input_recurring_rows",
                    "safely_resolved_rules",
                    "resolution_rate",
                    "materialized_future_occurrences",
                    "duplicate_delta",
                    "provenance_missing",
                    "promotions_without_provenance",
                    "existing_accepted_loss",
                    "publication_gate_passed",
                )
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if args.require_gates and not payload["publication_gate_passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
