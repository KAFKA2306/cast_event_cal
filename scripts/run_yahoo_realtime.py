from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts import fetch_yahoo_realtime as implementation

HISTORY_PATH = Path("public/yahoo-candidate-history.json")
HISTORY_RETENTION_DAYS = 30
AUTHOR_FROM_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:x|twitter)\.com/([^/]+)/status/\d+", re.IGNORECASE
)


def configure() -> None:
    # Python treats Japanese characters as word characters. A normal ``VRC\b``
    # therefore misses VRCイベント / VRC初心者. Reject only Latin continuations.
    implementation.VRCHAT_RE = re.compile(r"(?:#?vrchat|#?vrc)(?![a-z])", re.IGNORECASE)
    implementation.PARSER_VERSION = "1.4"


def read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def read_history(path: Path = HISTORY_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(value, dict):
        value = value.get("candidates", [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def author_from_url(url: str) -> str | None:
    match = AUTHOR_FROM_URL_RE.search(url)
    return match.group(1) if match else None


def observed_candidate(row: dict[str, Any], observed_at: datetime) -> dict[str, Any] | None:
    status_id = str(row.get("status_id") or "").strip()
    text = str(row.get("text") or row.get("text_excerpt") or "").strip()
    url = str(row.get("url") or f"https://x.com/i/web/status/{status_id}").strip()
    if not implementation.STATUS_ID_RE.fullmatch(status_id) or not text:
        return None
    retweet_count = row.get("retweet_count")
    try:
        retweet_count = int(retweet_count) if retweet_count is not None else None
    except (TypeError, ValueError):
        retweet_count = None
    stamp = implementation.utc_text(observed_at)
    return {
        "status_id": status_id,
        "url": url,
        "text": text,
        "author": row.get("author") or author_from_url(url),
        "retweet_count": retweet_count,
        "first_seen_at": str(row.get("first_seen_at") or stamp),
        "last_seen_at": str(row.get("last_seen_at") or stamp),
        "last_decision": str(row.get("last_decision") or "pending"),
        "last_reason": row.get("last_reason") or row.get("reason"),
    }


def merge_history(
    existing: list[dict[str, Any]], observed: list[dict[str, Any]], observed_at: datetime
) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in existing:
        normalized = observed_candidate(row, observed_at)
        if normalized:
            selected[normalized["status_id"]] = normalized
    stamp = implementation.utc_text(observed_at)
    for row in observed:
        normalized = observed_candidate(row, observed_at)
        if not normalized:
            continue
        current = selected.get(normalized["status_id"])
        if current:
            normalized["first_seen_at"] = current["first_seen_at"]
            old_retweets = current.get("retweet_count")
            new_retweets = normalized.get("retweet_count")
            if old_retweets is not None and (new_retweets is None or int(old_retweets) > int(new_retweets)):
                normalized["retweet_count"] = int(old_retweets)
        normalized["last_seen_at"] = stamp
        selected[normalized["status_id"]] = normalized
    lower = observed_at - timedelta(days=HISTORY_RETENTION_DAYS)
    kept: list[dict[str, Any]] = []
    for row in selected.values():
        seen = implementation.parse_instant(str(row.get("last_seen_at") or ""))
        if seen and seen >= lower:
            kept.append(row)
    return sorted(kept, key=lambda item: (str(item.get("first_seen_at")), str(item["status_id"])))


def reevaluate_history(
    history: list[dict[str, Any]], *, actual_now: datetime, min_retweets: int, x_ids: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    evaluated: list[dict[str, Any]] = []
    for row in history:
        # Relative expressions such as "本日" must use first observation time,
        # not the day on which a future parser version reprocesses the candidate.
        anchor = implementation.parse_instant(str(row.get("first_seen_at") or "")) or actual_now
        candidate = {
            "status_id": row["status_id"],
            "url": row.get("url"),
            "text": row.get("text"),
            "author": row.get("author"),
            "retweet_count": row.get("retweet_count"),
        }
        event, reason = implementation.candidate_to_event(
            candidate, now=anchor, min_retweets=min_retweets, x_ids=x_ids
        )
        updated = dict(row)
        if event:
            updated["last_decision"] = "accepted"
            updated["last_reason"] = None
            accepted.append(event)
        else:
            rejection = reason or "unknown"
            updated["last_decision"] = "rejected"
            updated["last_reason"] = rejection
            rejected.append(
                {
                    "status_id": row["status_id"],
                    "url": row.get("url"),
                    "reason": rejection,
                    "retweet_count": row.get("retweet_count"),
                    "first_seen_at": row.get("first_seen_at"),
                    "last_seen_at": row.get("last_seen_at"),
                    "text_excerpt": str(row.get("text") or "")[:360],
                }
            )
        evaluated.append(updated)
    return accepted, rejected, evaluated


def write_history(history: list[dict[str, Any]], path: Path = HISTORY_PATH) -> None:
    implementation.write_json(
        path,
        {
            "schema_version": "1.0",
            "retention_days": HISTORY_RETENTION_DAYS,
            "generated_at": implementation.utc_text(datetime.now(UTC)),
            "candidate_count": len(history),
            "candidates": history,
        },
    )


def main() -> int:
    configure()
    actual_now = datetime.now(UTC).replace(microsecond=0)
    previous_health = read_object(implementation.HEALTH_PATH)
    previous_observed_at = implementation.parse_instant(str(previous_health.get("generated_at") or "")) or actual_now
    history = read_history()
    # Seed the durable ledger from previously rejected rows when migrating from
    # the old one-run-only format.
    history = merge_history(history, implementation.read_array(implementation.REJECTED_PATH), previous_observed_at)

    captured: list[dict[str, Any]] = []
    original_extract = implementation.extract_candidates

    def capture(html_text: str) -> list[dict[str, Any]]:
        rows = original_extract(html_text)
        captured.extend(rows)
        return rows

    implementation.extract_candidates = capture
    try:
        result = implementation.main()
    finally:
        implementation.extract_candidates = original_extract

    history = merge_history(history, captured, actual_now)
    min_retweets = int(os.environ.get("YAHOO_MIN_RETWEETS", "3"))
    x_ids = implementation.known_x_ids(implementation.read_array(implementation.X_EVENTS_PATH))
    accepted, rejected, evaluated = reevaluate_history(
        history, actual_now=actual_now, min_retweets=min_retweets, x_ids=x_ids
    )
    before = implementation.read_array(implementation.OUTPUT_PATH)
    merged = implementation.merge_cache(before, accepted, actual_now)
    promoted = {
        str(item.get("source_id")) for item in accepted
    } - {str(item.get("source_id")) for item in before}
    implementation.write_json(implementation.OUTPUT_PATH, merged)
    implementation.write_json(implementation.REJECTED_PATH, rejected[:500])
    write_history(evaluated)

    health = read_object(implementation.HEALTH_PATH)
    health.update(
        {
            "parser_version": implementation.PARSER_VERSION,
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
        "Yahoo history: "
        f"candidates={len(evaluated)} accepted={len(accepted)} "
        f"rejected={len(rejected)} promoted={len(promoted)} events={len(merged)}"
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
