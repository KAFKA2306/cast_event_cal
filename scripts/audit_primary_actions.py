from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENTS = ROOT / "public" / "events.json"
DEFAULT_REPORT = ROOT / "public" / "primary-action-audit.json"
ACTIONABLE_LINK_KINDS = frozenset({"application", "participation", "vrchat_group", "vrchat_world", "announcement", "official_web", "official_website"})


def _https(value: Any) -> str | None:
    value = str(value or "").strip()
    return value if value.startswith("https://") else None


def actionable_official_links(event: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in event.get("official_links") or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "").strip()
        url = _https(row.get("url"))
        if kind in ACTIONABLE_LINK_KINDS and url:
            rows.append({"kind": kind, "url": url})
    return rows


def audit(events: list[dict[str, Any]]) -> dict[str, Any]:
    dangling_kind: list[str] = []
    missing_action: list[str] = []
    invalid_action: list[str] = []
    for event in events:
        event_id = str(event.get("id") or "")
        action_url = _https(event.get("primary_action_url"))
        action_kind = str(event.get("primary_action_kind") or "").strip()
        if event.get("primary_action_url") and not action_url:
            invalid_action.append(event_id)
        if action_kind and not action_url:
            dangling_kind.append(event_id)
        if not action_url and actionable_official_links(event):
            missing_action.append(event_id)

    failures = {
        "dangling_primary_action_kind": sorted(dangling_kind),
        "invalid_primary_action_url": sorted(invalid_action),
        "actionable_official_link_without_primary_action": sorted(missing_action),
    }
    failure_count = sum(len(rows) for rows in failures.values())
    return {
        "schema_version": "1.0",
        "status": "ok" if failure_count == 0 else "error",
        "event_count": len(events),
        "failure_count": failure_count,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit canonical primary-action invariants")
    parser.add_argument("events", nargs="?", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    payload = json.loads(args.events.read_text(encoding="utf-8"))
    events = payload.get("events") if isinstance(payload, dict) else payload
    if not isinstance(events, list):
        raise ValueError("events payload must contain a list")
    report = audit([row for row in events if isinstance(row, dict)])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Primary action audit: status={report['status']} failures={report['failure_count']}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
