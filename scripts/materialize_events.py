from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def parse_instant(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def utc_text(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_clock(value: str) -> time:
    return time.fromisoformat(value)


def event_for_date(template: dict[str, Any], local_day: date) -> dict[str, Any]:
    schedule = template["schedule"]
    zone = ZoneInfo(schedule.get("timezone", "Asia/Tokyo"))
    start = datetime.combine(local_day, parse_clock(schedule["start_time"]), zone)
    end: datetime | None = None
    if schedule.get("end_time"):
        end = datetime.combine(local_day, parse_clock(schedule["end_time"]), zone)
        if end <= start:
            end += timedelta(days=1)
    series_id = str(template["series_id"])
    event = {
        "source_id": f"{series_id}:{local_day.isoformat()}",
        "title": template["title"],
        "starts_at": utc_text(start),
        "organizer": template.get("organizer"),
        "location": template.get("location"),
        "description": template.get("description"),
        "url": template.get("url"),
        "category": template.get("category"),
        "tags": list(template.get("tags") or []),
        "confidence": 1.0,
        "review_required": False,
    }
    if end:
        event["ends_at"] = utc_text(end)
    return {key: value for key, value in event.items() if value is not None}


def materialize_weekly(template: dict[str, Any], first_day: date, last_day: date) -> list[dict[str, Any]]:
    weekdays = {WEEKDAYS[item] for item in template["schedule"].get("weekdays", [])}
    if not weekdays:
        raise ValueError(f"{template['series_id']}: weekly schedule has no weekdays")
    result: list[dict[str, Any]] = []
    current = first_day
    while current <= last_day:
        if current.weekday() in weekdays:
            result.append(event_for_date(template, current))
        current += timedelta(days=1)
    return result


def materialize_monthly_nth_weekday(template: dict[str, Any], first_day: date, last_day: date) -> list[dict[str, Any]]:
    schedule = template["schedule"]
    weekday = WEEKDAYS[schedule["weekday"]]
    nth = int(schedule["nth"])
    if nth == 0 or not -5 <= nth <= 5:
        raise ValueError(f"{template['series_id']}: nth must be between -5 and 5 excluding 0")
    result: list[dict[str, Any]] = []
    cursor = first_day.replace(day=1)
    while cursor <= last_day:
        if cursor.month == 12:
            next_month = cursor.replace(year=cursor.year + 1, month=1)
        else:
            next_month = cursor.replace(month=cursor.month + 1)
        matching_days: list[date] = []
        day = cursor
        while day < next_month:
            if day.weekday() == weekday:
                matching_days.append(day)
            day += timedelta(days=1)
        try:
            occurrence = matching_days[nth - 1] if nth > 0 else matching_days[nth]
        except IndexError:
            occurrence = None
        if occurrence and first_day <= occurrence <= last_day:
            result.append(event_for_date(template, occurrence))
        cursor = next_month
    return result


def materialize(
    recurring: list[dict[str, Any]],
    one_off: list[dict[str, Any]],
    *,
    now: datetime,
    past_days: int,
    future_days: int,
) -> list[dict[str, Any]]:
    lower = now.astimezone(UTC) - timedelta(days=past_days)
    upper = now.astimezone(UTC) + timedelta(days=future_days)
    first_day = lower.astimezone(ZoneInfo("Asia/Tokyo")).date()
    last_day = upper.astimezone(ZoneInfo("Asia/Tokyo")).date()

    events: list[dict[str, Any]] = []
    for template in recurring:
        frequency = template.get("schedule", {}).get("frequency")
        if frequency == "weekly":
            events.extend(materialize_weekly(template, first_day, last_day))
        elif frequency == "monthly_nth_weekday":
            events.extend(materialize_monthly_nth_weekday(template, first_day, last_day))
        else:
            raise ValueError(f"{template.get('series_id')}: unsupported frequency {frequency}")

    for event in one_off:
        start = parse_instant(str(event["starts_at"]))
        if lower <= start <= upper:
            events.append(dict(event))

    unique: dict[str, dict[str, Any]] = {}
    for event in events:
        source_id = str(event["source_id"])
        if source_id in unique:
            raise ValueError(f"duplicate source_id: {source_id}")
        unique[source_id] = event
    return sorted(unique.values(), key=lambda item: (parse_instant(str(item["starts_at"])), str(item["title"])))


def read_array(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{path} must contain an array of objects")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize rolling VRChat event occurrences")
    parser.add_argument("--recurring", type=Path, default=Path("data/recurring_events.json"))
    parser.add_argument("--one-off", type=Path, default=Path("data/one_off_events.json"))
    parser.add_argument("--output", type=Path, default=Path("data/manual_events.json"))
    parser.add_argument("--past-days", type=int, default=1)
    parser.add_argument("--future-days", type=int, default=120)
    parser.add_argument("--now", help="ISO 8601 instant for deterministic validation")
    args = parser.parse_args()

    now = parse_instant(args.now) if args.now else datetime.now(UTC).replace(microsecond=0)
    events = materialize(
        read_array(args.recurring),
        read_array(args.one_off),
        now=now,
        past_days=args.past_days,
        future_days=args.future_days,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"materialized {len(events)} events to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
