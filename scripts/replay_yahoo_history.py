from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import fetch_yahoo_realtime as implementation
from scripts.run_yahoo_realtime import (
    HISTORY_RETENTION_DAYS,
    configure,
    merge_history,
    read_history,
    read_object,
    reevaluate_history,
    write_history,
)


def main() -> int:
    """Re-evaluate the durable Yahoo ledger without making a network request."""
    configure()
    actual_now = datetime.now(UTC).replace(microsecond=0)
    previous_health = read_object(implementation.HEALTH_PATH)
    previous_observed_at = implementation.parse_instant(str(previous_health.get("generated_at") or "")) or actual_now

    history = read_history()
    history = merge_history(
        history,
        implementation.read_array(implementation.REJECTED_PATH),
        previous_observed_at,
    )
    min_retweets = int(os.environ.get("YAHOO_MIN_RETWEETS", "3"))
    x_ids = implementation.known_x_ids(implementation.read_array(implementation.X_EVENTS_PATH))
    accepted, rejected, evaluated = reevaluate_history(
        history,
        actual_now=actual_now,
        min_retweets=min_retweets,
        x_ids=x_ids,
    )

    before = implementation.read_array(implementation.OUTPUT_PATH)
    merged = implementation.merge_cache(before, accepted, actual_now)
    promoted = {
        str(item.get("source_id")) for item in accepted
    } - {str(item.get("source_id")) for item in before}
    implementation.write_json(implementation.OUTPUT_PATH, merged)
    implementation.write_json(implementation.REJECTED_PATH, rejected[:500])
    write_history(evaluated)

    health = previous_health
    health.update(
        {
            "parser_version": implementation.PARSER_VERSION,
            "history_replay_mode": "ledger_only",
            "history_retention_days": HISTORY_RETENTION_DAYS,
            "history_candidate_count": len(evaluated),
            "history_accepted_count": len(accepted),
            "history_rejected_count": len(rejected),
            "automatically_promoted_count": len(promoted),
            "event_count": len(merged),
        }
    )
    implementation.write_json(implementation.HEALTH_PATH, health)
    print(
        "Yahoo ledger replay: "
        f"candidates={len(evaluated)} accepted={len(accepted)} "
        f"rejected={len(rejected)} promoted={len(promoted)} events={len(merged)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
