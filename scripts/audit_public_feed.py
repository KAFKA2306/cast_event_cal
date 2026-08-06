from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "cast-event-cal.public-feed-audit.v1"


def _load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _event_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        events = payload
    elif isinstance(payload, dict) and isinstance(payload.get("events"), list):
        events = payload["events"]
    else:
        raise ValueError("events.json must be a JSON array or an object with an events array")
    if not all(isinstance(item, dict) for item in events):
        raise ValueError("every event must be a JSON object")
    return events


def _identity(event: dict[str, Any]) -> str | None:
    for key in ("id", "event_id", "uid", "canonical_id"):
        value = event.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return f"{key}:{str(value).strip()}"
    url = event.get("url") or event.get("source_url") or event.get("official_url")
    start = event.get("start") or event.get("start_at") or event.get("start_datetime")
    title = event.get("title") or event.get("name")
    if all(isinstance(value, str) and value.strip() for value in (url, start, title)):
        return "fallback:" + "|".join(value.strip() for value in (url, start, title))
    return None


def _parse_datetime(value: str) -> bool:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return True


def audit(path: Path) -> dict[str, Any]:
    payload = _load(path)
    events = _event_list(payload)
    errors: list[dict[str, Any]] = []
    identities: list[str] = []

    for index, event in enumerate(events):
        identity = _identity(event)
        if identity is None:
            errors.append({"index": index, "code": "missing_identity", "message": "event has no stable identity"})
        else:
            identities.append(identity)

        title = event.get("title") or event.get("name")
        if not isinstance(title, str) or not title.strip():
            errors.append({"index": index, "code": "missing_title", "message": "event title is empty"})

        for key in ("start", "start_at", "start_datetime"):
            if key in event:
                value = event[key]
                if not isinstance(value, str) or not _parse_datetime(value):
                    errors.append({"index": index, "code": "invalid_datetime", "field": key, "message": "datetime is not ISO-8601"})
                break

        for key in ("url", "source_url", "official_url"):
            if key in event:
                value = event[key]
                if value is not None and (not isinstance(value, str) or not value.startswith(("https://", "http://"))):
                    errors.append({"index": index, "code": "invalid_url", "field": key, "message": "URL must be absolute HTTP(S)"})

    for identity, count in sorted(Counter(identities).items()):
        if count > 1:
            errors.append({"code": "duplicate_identity", "identity": identity, "count": count})

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "input": str(path),
        "sha256": digest,
        "event_count": len(events),
        "unique_identity_count": len(set(identities)),
        "error_count": len(errors),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the published event feed without network access")
    parser.add_argument("path", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = audit(args.path)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if report["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
