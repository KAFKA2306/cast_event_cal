from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REJECTED_PATH = Path("data/yahoo_realtime_rejected.json")
OUTPUT_PATH = Path("public/yahoo-rejection-sample-audit.json")
SAMPLES_PER_REASON = 5


def read_rows(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("Yahoo rejected payload must be an array")
    return [row for row in value if isinstance(row, dict)]


def sample_key(row: dict[str, Any]) -> tuple[int, str, str]:
    try:
        retweets = int(row.get("retweet_count") or 0)
    except (TypeError, ValueError):
        retweets = 0
    return (-retweets, str(row.get("last_seen_at") or ""), str(row.get("status_id") or ""))


def public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "status_id": str(row.get("status_id") or ""),
        "url": str(row.get("url") or ""),
        "retweet_count": int(row.get("retweet_count") or 0),
        "source_created_at": row.get("source_created_at"),
        "first_seen_at": row.get("first_seen_at"),
        "last_seen_at": row.get("last_seen_at"),
        "text_excerpt": str(row.get("text_excerpt") or "")[:360],
    }


def build(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("reason") or "unknown")].append(row)
    reasons = []
    for reason in sorted(grouped):
        items = sorted(grouped[reason], key=sample_key)
        reasons.append(
            {
                "reason": reason,
                "count_in_materialized_rejected_file": len(items),
                "samples": [public_row(row) for row in items[:SAMPLES_PER_REASON]],
            }
        )
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": str(REJECTED_PATH),
        "sampling_policy": "up_to_5_per_reason_sorted_by_retweets_desc_then_observation",
        "materialized_rejected_count": len(rows),
        "reason_count": len(reasons),
        "reasons": reasons,
    }


def main() -> int:
    payload = build(read_rows(REJECTED_PATH))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Yahoo rejection sample audit: reasons={payload['reason_count']} rows={payload['materialized_rejected_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
