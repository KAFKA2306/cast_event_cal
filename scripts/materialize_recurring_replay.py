from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from scripts import collect_yahoo_corpus as corpus
from scripts import fetch_yahoo_realtime as implementation
from scripts.audit_recurring_replay import read_candidates

DEFAULT_REPLAY = Path("audit/recurring-replay.json")
DEFAULT_CANDIDATES = Path("public/yahoo-candidate-history.json")
DEFAULT_EVENTS = Path("data/yahoo_realtime_events.json")


def materialize(
    candidates: list[dict[str, Any]],
    report: dict[str, Any],
    existing: list[dict[str, Any]],
    *,
    now: datetime,
    min_retweets: int,
    x_ids: set[str],
    builder: Callable[..., tuple[dict[str, Any] | None, str | None]] = corpus.refined_candidate_to_event_at,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if int(report.get("promotions_without_provenance") or 0):
        raise ValueError("recurring replay has promotions without provenance")

    by_status = {str(row.get("status_id") or ""): row for row in candidates if row.get("status_id")}
    generated: list[dict[str, Any]] = []
    rejected = 0
    for result in report.get("results") or []:
        if not isinstance(result, dict) or not result.get("resolved"):
            continue
        status_id = str(result.get("status_id") or "")
        candidate = by_status.get(status_id)
        if candidate is None or not (status_id or result.get("url")):
            rejected += 1
            continue
        starts = result.get("future_starts") or []
        if not starts:
            continue
        event_at = implementation.parse_instant(str(starts[0]))
        event, _reason = builder(
            candidate,
            event_at=event_at,
            now=now,
            min_retweets=min_retweets,
            x_ids=x_ids,
        )
        if event is None:
            rejected += 1
            continue
        event["recurrence_resolver_version"] = str(report.get("resolver_version") or "")
        event["recurrence_rule"] = result.get("rule")
        event["recurrence_provenance_url"] = str(result.get("url") or candidate.get("url") or "")
        tags = list(event.get("tags") or [])
        if "定期開催" not in tags:
            tags.append("定期開催")
        event["tags"] = tags
        generated.append(event)

    merged = implementation.merge_cache(existing, generated, now)
    return merged, {
        "resolved_rows": sum(bool(row.get("resolved")) for row in report.get("results") or [] if isinstance(row, dict)),
        "materialized": len(generated),
        "rejected": rejected,
        "output_events": len(merged),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    args = parser.parse_args()

    corpus.configure_classifier()
    report = json.loads(args.replay.read_text(encoding="utf-8"))
    candidates = read_candidates(args.candidates)
    existing = implementation.read_array(args.events)
    now = datetime.now(UTC).replace(microsecond=0)
    x_ids = implementation.known_x_ids(implementation.read_array(implementation.X_EVENTS_PATH))
    merged, stats = materialize(
        candidates,
        report,
        existing,
        now=now,
        min_retweets=int(os.environ.get("YAHOO_MIN_RETWEETS", "3")),
        x_ids=x_ids,
    )
    implementation.write_json(args.events, merged)
    print(json.dumps(stats, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
