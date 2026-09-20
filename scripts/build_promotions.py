from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
ALLOWED_TYPES = {"featured"}
ALLOWED_STATUSES = {"approved", "paused", "draft"}
ALLOWED_PLACEMENTS = {"home", "tonight", "category"}


def parse_time(value: object) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("promotion timestamp is required")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("promotion timestamp must include timezone")
    return parsed


def https_url(value: object) -> str:
    raw = str(value or "").strip()
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    return raw if parsed.scheme == "https" and parsed.netloc else ""


def event_destinations(event: dict[str, object]) -> set[str]:
    rows: set[str] = set()
    for value in (event.get("primary_action_url"), event.get("url")):
        if url := https_url(value):
            rows.add(url)
    for item in event.get("official_links") or []:
        if isinstance(item, dict):
            if url := https_url(item.get("url")):
                rows.add(url)
    return rows


def validate_promotion(
    row: dict[str, object],
    events_by_id: dict[str, dict[str, object]],
) -> dict[str, object]:
    promotion_id = str(row.get("promotion_id") or "").strip()
    campaign_id = str(row.get("campaign_id") or "").strip()
    event_id = str(row.get("event_id") or "").strip()
    promotion_type = str(row.get("type") or "").strip()
    status = str(row.get("status") or "").strip()

    for name, value in (
        ("promotion_id", promotion_id),
        ("campaign_id", campaign_id),
        ("event_id", event_id),
    ):
        if not SAFE_ID.fullmatch(value):
            raise ValueError(f"invalid {name}: {value!r}")

    if promotion_type not in ALLOWED_TYPES:
        raise ValueError(f"unsupported promotion type: {promotion_type!r}")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"invalid promotion status: {status!r}")

    event = events_by_id.get(event_id)
    if event is None:
        raise ValueError(f"promotion event_id not found in canonical events: {event_id}")

    starts_at = parse_time(row.get("starts_at"))
    ends_at = parse_time(row.get("ends_at"))
    if ends_at <= starts_at:
        raise ValueError(f"promotion ends_at must be after starts_at: {promotion_id}")

    destination_url = https_url(row.get("destination_url"))
    if not destination_url:
        raise ValueError(f"promotion destination_url must be https: {promotion_id}")
    if destination_url not in event_destinations(event):
        raise ValueError(
            "promotion destination_url must be one of the canonical event action URLs: "
            f"{promotion_id}"
        )

    placements_raw = row.get("placements")
    if not isinstance(placements_raw, list) or not placements_raw:
        raise ValueError(f"promotion placements must be a non-empty list: {promotion_id}")
    placements = [str(value).strip() for value in placements_raw]
    if any(value not in ALLOWED_PLACEMENTS for value in placements):
        raise ValueError(f"unsupported promotion placement: {promotion_id}")
    placements = list(dict.fromkeys(placements))

    label = str(row.get("label") or "Featured").strip() or "Featured"
    if len(label) > 40:
        raise ValueError(f"promotion label is too long: {promotion_id}")

    return {
        "promotion_id": promotion_id,
        "campaign_id": campaign_id,
        "event_id": event_id,
        "type": promotion_type,
        "label": label,
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "destination_url": destination_url,
        "placements": placements,
        "status": status,
    }


def build_promotions(
    config_path: Path,
    events_path: Path,
    output_path: Path,
    script_source: Path | None = None,
    script_output: Path | None = None,
) -> dict[str, int]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if str(config.get("schema_version")) != "1.0":
        raise ValueError("promotion schema_version must be 1.0")
    raw_promotions = config.get("promotions")
    if not isinstance(raw_promotions, list):
        raise ValueError("promotions must be a list")

    events_payload = json.loads(events_path.read_text(encoding="utf-8"))
    events = events_payload.get("events")
    if not isinstance(events, list):
        raise ValueError("events.json events must be a list")
    events_by_id = {
        str(row.get("id")): row
        for row in events
        if isinstance(row, dict) and row.get("id")
    }

    validated = [
        validate_promotion(row, events_by_id)
        for row in raw_promotions
        if isinstance(row, dict)
    ]
    promotion_ids = [str(row["promotion_id"]) for row in validated]
    campaign_ids = [str(row["campaign_id"]) for row in validated]
    if len(promotion_ids) != len(set(promotion_ids)):
        raise ValueError("promotion_id must be unique")
    if len(campaign_ids) != len(set(campaign_ids)):
        raise ValueError("campaign_id must be unique")

    approved = [row for row in validated if row["status"] == "approved"]
    approved.sort(key=lambda row: (str(row["starts_at"]), str(row["promotion_id"])))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {"schema_version": "1.0", "promotions": approved},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if script_source is not None or script_output is not None:
        if script_source is None or script_output is None:
            raise ValueError("script_source and script_output must be provided together")
        script_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(script_source, script_output)

    return {
        "configured": len(validated),
        "approved": len(approved),
        "published": len(approved),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/promotions.json"))
    parser.add_argument("--events", type=Path, default=Path("public/events.json"))
    parser.add_argument("--output", type=Path, default=Path("public/promotions.json"))
    parser.add_argument("--script-source", type=Path, default=Path("web/promotions.js"))
    parser.add_argument("--script-output", type=Path, default=Path("public/promotions.js"))
    args = parser.parse_args()
    result = build_promotions(
        args.config,
        args.events,
        args.output,
        args.script_source,
        args.script_output,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
