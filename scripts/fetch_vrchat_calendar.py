from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

SEARCH_API_URL = "https://api.vrchat.cloud/api/1/calendar/search"
DISCOVER_API_URL = "https://api.vrchat.cloud/api/1/calendar/discover"
USER_AGENT = "cast-event-cal/2.2 (+https://github.com/KAFKA2306/cast_event_cal)"
DEFAULT_TERMS = ["日本語", "初心者", "交流", "音楽", "ゲーム", "Quest"]


def utc_text(value: datetime | None = None) -> str:
    instant = value or datetime.now(UTC)
    return instant.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{path} must contain an array of objects")
    return data


def normalize_cookie(value: str) -> str:
    token = value.strip()
    if token.startswith("auth="):
        token = token[5:]
    if not token or any(char in token for char in "\r\n;"):
        raise ValueError("invalid VRCHAT_AUTH_COOKIE")
    return token


def semantic_key(event: dict[str, Any]) -> tuple[str, str]:
    title = re.sub(r"\s+", " ", str(event.get("title") or "")).strip().casefold()
    starts_at = str(event.get("starts_at") or event.get("startsAt") or "")
    return title, starts_at


def event_url(item: dict[str, Any]) -> str | None:
    owner_id = str(item.get("ownerId") or "")
    event_id = str(item.get("id") or "")
    if owner_id.startswith("grp_") and event_id.startswith("cal_"):
        return f"https://vrchat.com/home/group/{owner_id}/calendar/{event_id}"
    return None


def normalize_event(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("isDraft") or item.get("deletedAt"):
        return None
    if item.get("accessType") != "public":
        return None
    event_id = str(item.get("id") or "")
    title = str(item.get("title") or "").strip()
    starts_at = str(item.get("startsAt") or "")
    if not event_id.startswith("cal_") or not title or not starts_at:
        return None

    owner_id = str(item.get("ownerId") or "") or None
    tags = {
        "VRChat",
        "公式カレンダー",
        str(item.get("category") or "").strip(),
        *(str(value).strip() for value in item.get("tags") or []),
        *(str(value).strip() for value in item.get("languages") or []),
        *(str(value).strip() for value in item.get("platforms") or []),
    }
    if item.get("featured"):
        tags.add("featured")
    occurrence_kind = str(item.get("occurrenceKind") or "").strip()
    if occurrence_kind:
        tags.add(occurrence_kind)
    event: dict[str, Any] = {
        "source_id": event_id,
        "title": title,
        "starts_at": starts_at,
        "ends_at": item.get("endsAt"),
        "organizer": owner_id,
        "location": "VRChat Public Calendar",
        "description": item.get("description"),
        "url": event_url(item),
        "image_url": item.get("imageUrl"),
        "category": item.get("category"),
        "status": "scheduled",
        "tags": sorted(value for value in tags if value),
        "confidence": 1.0,
        "review_required": False,
    }
    return {key: value for key, value in event.items() if value is not None}


def checked_results(payload: Any, *, route: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError(f"VRChat calendar {route} returned a non-object response")
    page = payload.get("results", [])
    if not isinstance(page, list):
        raise ValueError(f"VRChat calendar {route} returned an invalid results field")
    return [item for item in page if isinstance(item, dict)], payload


def fetch_discover(client: httpx.Client, *, page_size: int, max_pages: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(max_pages):
        if cursor:
            params: dict[str, Any] = {"n": page_size, "nextCursor": cursor}
        else:
            params = {
                "scope": "upcoming",
                "featuredResults": "include",
                "nonFeaturedResults": "include",
                "personalizedResults": "include",
                "minimumRemainingMinutes": 0,
                "n": page_size,
            }
        response = client.get(DISCOVER_API_URL, params=params)
        response.raise_for_status()
        page, payload = checked_results(response.json(), route="discovery")
        rows.extend(page)
        next_cursor = payload.get("nextCursor")
        if not page or not isinstance(next_cursor, str) or not next_cursor.strip():
            break
        cursor = next_cursor
    return rows


def fetch_term(client: httpx.Client, *, term: str, page_size: int, max_pages: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    for _ in range(max_pages):
        response = client.get(
            SEARCH_API_URL,
            params={"searchTerm": term, "utcOffset": 9, "n": page_size, "offset": offset},
        )
        response.raise_for_status()
        page, payload = checked_results(response.json(), route="search")
        rows.extend(page)
        if not payload.get("hasNext") or len(page) < page_size:
            break
        offset += page_size
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_preserved_health(
    *,
    health_output: Path,
    generated_at: str,
    existing_count: int,
    status: str,
    reason: str,
    query_count: int,
    errors: list[str],
) -> None:
    write_json(
        health_output,
        {
            "schema_version": "1.1",
            "generated_at": generated_at,
            "status": status,
            "reason": reason,
            "event_count": existing_count,
            "query_count": query_count,
            "routes": {"discover": 0, "search": 0},
            "errors": errors,
        },
    )


def run_discovery(
    *,
    cookie: str | None,
    output: Path,
    health_output: Path,
    exclude: Path,
    terms: list[str],
    page_size: int,
    max_pages: int,
    timeout: float,
) -> int:
    generated_at = utc_text()
    existing = read_array(output)
    excluded_keys = {semantic_key(item) for item in read_array(exclude)}

    if not cookie:
        if not output.exists():
            write_json(output, [])
        write_preserved_health(
            health_output=health_output,
            generated_at=generated_at,
            existing_count=len(existing),
            status="skipped",
            reason="VRCHAT_AUTH_COOKIE is not configured",
            query_count=0,
            errors=[],
        )
        print("VRChat calendar discovery skipped: VRCHAT_AUTH_COOKIE is not configured")
        return 0

    try:
        token = normalize_cookie(cookie)
    except ValueError as exc:
        write_preserved_health(
            health_output=health_output,
            generated_at=generated_at,
            existing_count=len(existing),
            status="degraded",
            reason="invalid credential; preserved previous discovery cache",
            query_count=0,
            errors=[str(exc)],
        )
        print(f"VRChat calendar discovery preserved {len(existing)} cached events")
        return 0

    errors: list[str] = []
    raw_rows: list[dict[str, Any]] = []
    route_counts = {"discover": 0, "search": 0}
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Cookie": f"auth={token}"},
    ) as client:
        try:
            discovered = fetch_discover(client, page_size=page_size, max_pages=max_pages)
            raw_rows.extend(discovered)
            route_counts["discover"] = len(discovered)
        except Exception as exc:
            errors.append(f"discover: {type(exc).__name__}: {exc}")
        for term in terms:
            try:
                searched = fetch_term(client, term=term, page_size=page_size, max_pages=max_pages)
                raw_rows.extend(searched)
                route_counts["search"] += len(searched)
            except Exception as exc:
                errors.append(f"search:{term}: {type(exc).__name__}: {exc}")

    events_by_id: dict[str, dict[str, Any]] = {}
    for item in raw_rows:
        event = normalize_event(item)
        if event is None or semantic_key(event) in excluded_keys:
            continue
        events_by_id[str(event["source_id"])] = event
    events = sorted(events_by_id.values(), key=lambda item: (str(item["starts_at"]), str(item["title"])))

    if errors and not events:
        write_preserved_health(
            health_output=health_output,
            generated_at=generated_at,
            existing_count=len(existing),
            status="degraded",
            reason="all live routes failed; preserved previous discovery cache",
            query_count=len(terms),
            errors=errors,
        )
        print(f"VRChat calendar discovery preserved {len(existing)} cached events")
        return 0

    write_json(output, events)
    write_json(
        health_output,
        {
            "schema_version": "1.1",
            "generated_at": generated_at,
            "status": "ok" if not errors else "degraded",
            "event_count": len(events),
            "query_count": len(terms),
            "raw_result_count": len(raw_rows),
            "routes": route_counts,
            "errors": errors,
        },
    )
    print(
        f"discovered {len(events)} public VRChat calendar events "
        f"(discover={route_counts['discover']}, search={route_counts['search']})"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover public VRChat calendar events")
    parser.add_argument("--output", type=Path, default=Path("data/discovered_events.json"))
    parser.add_argument("--health-output", type=Path, default=Path("data/discovery_health.json"))
    parser.add_argument("--exclude", type=Path, default=Path("data/manual_events.json"))
    parser.add_argument("--term", action="append", dest="terms")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=25.0)
    args = parser.parse_args()
    if not 1 <= args.page_size <= 100:
        parser.error("--page-size must be between 1 and 100")
    if not 1 <= args.max_pages <= 10:
        parser.error("--max-pages must be between 1 and 10")
    terms = [term.strip() for term in (args.terms or DEFAULT_TERMS) if term.strip()]
    if not terms:
        parser.error("at least one non-empty search term is required")
    return run_discovery(
        cookie=os.environ.get("VRCHAT_AUTH_COOKIE"),
        output=args.output,
        health_output=args.health_output,
        exclude=args.exclude,
        terms=terms,
        page_size=args.page_size,
        max_pages=args.max_pages,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
