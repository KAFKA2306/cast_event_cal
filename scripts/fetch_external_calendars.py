from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
import yaml
from dateutil import parser as date_parser
from dateutil.rrule import rrulestr

JST = ZoneInfo("Asia/Tokyo")
USER_AGENT = "cast-event-cal/2.2 (+https://github.com/KAFKA2306/cast_event_cal)"
DEFAULT_TIMEOUT = 25.0
OFFICIAL_LINK_KINDS = {"official_website", "event_home", "announcement", "official_event_page"}
BLOCKED_JSONLD_HOSTS = {
    "x.com",
    "twitter.com",
    "vrchat.com",
    "discord.com",
    "discord.gg",
    "forms.gle",
    "docs.google.com",
}


class ExternalSourceError(RuntimeError):
    pass


@dataclass(slots=True)
class SourceResult:
    name: str
    source_type: str
    status: str
    count: int
    error: str | None = None
    stale_cache_count: int = 0
    source_page: str | None = None
    policy_url: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def utc_text(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on", "approved"}


def read_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError(f"{path} must contain an array of objects")
    return payload


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict) or not isinstance(payload.get("sources", []), list):
        raise ValueError("external source configuration must contain a sources array")
    return payload


def safe_zoneinfo(value: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(value or "Asia/Tokyo")
    except ZoneInfoNotFoundError:
        return JST


def parse_datetime(value: str | datetime, *, default_timezone: str = "Asia/Tokyo") -> datetime:
    parsed = value if isinstance(value, datetime) else date_parser.isoparse(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=safe_zoneinfo(default_timezone))
    return parsed.astimezone(UTC)


def normalize_datetime(value: str | datetime, *, default_timezone: str = "Asia/Tokyo") -> str:
    return parse_datetime(value, default_timezone=default_timezone).isoformat().replace("+00:00", "Z")


def unfold_ics(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def decode_ics_value(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def parse_ics_property(line: str) -> tuple[str, dict[str, str], str] | None:
    if ":" not in line:
        return None
    left, value = line.split(":", 1)
    pieces = left.split(";")
    params: dict[str, str] = {}
    for piece in pieces[1:]:
        if "=" in piece:
            key, param_value = piece.split("=", 1)
            params[key.upper()] = param_value.strip('"')
    return pieces[0].upper(), params, value


def parse_ics_datetime(value: str, params: dict[str, str], *, default_timezone: str) -> datetime:
    timezone = safe_zoneinfo(params.get("TZID") or default_timezone)
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value[:8], "%Y%m%d").replace(tzinfo=timezone).astimezone(UTC)
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    fmt = "%Y%m%dT%H%M%S" if len(value) >= 15 else "%Y%m%dT%H%M"
    return datetime.strptime(value, fmt).replace(tzinfo=timezone).astimezone(UTC)


def property_first(block: dict[str, list[tuple[dict[str, str], str]]], name: str) -> tuple[dict[str, str], str] | None:
    values = block.get(name, [])
    return values[0] if values else None


def organizer_from_ics(block: dict[str, list[tuple[dict[str, str], str]]]) -> str | None:
    item = property_first(block, "ORGANIZER")
    if not item:
        return None
    params, value = item
    return clean_text(params.get("CN") or value.removeprefix("mailto:")) or None


def stable_source_id(source: str, raw_id: str | None, title: str, starts_at: str, url: str | None) -> str:
    if raw_id:
        return raw_id
    payload = "|".join([source, clean_text(title).casefold(), starts_at, clean_text(url)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def parse_ics_events(
    text: str,
    *,
    source_name: str,
    fetched_at: str,
    source_page: str | None,
    tags: Iterable[str],
    default_timezone: str,
    window_start: datetime,
    window_end: datetime,
    max_events: int,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, list[tuple[dict[str, str], str]]]] = []
    current: dict[str, list[tuple[dict[str, str], str]]] | None = None
    for line in unfold_ics(text):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            blocks.append(current)
            current = None
        elif current is not None and (parsed := parse_ics_property(line)):
            name, params, value = parsed
            current.setdefault(name, []).append((params, value))

    output: dict[str, dict[str, Any]] = {}
    for block in blocks:
        start_item = property_first(block, "DTSTART")
        summary_item = property_first(block, "SUMMARY")
        if not start_item or not summary_item:
            continue
        start = parse_ics_datetime(start_item[1], start_item[0], default_timezone=default_timezone)
        end_item = property_first(block, "DTEND")
        end = parse_ics_datetime(end_item[1], end_item[0], default_timezone=default_timezone) if end_item else None
        duration = end - start if end else None
        uid_item = property_first(block, "UID")
        uid = clean_text(uid_item[1]) if uid_item else None
        title = decode_ics_value(summary_item[1])
        description_item = property_first(block, "DESCRIPTION")
        location_item = property_first(block, "LOCATION")
        url_item = property_first(block, "URL")
        status_item = property_first(block, "STATUS")
        recurrence_item = property_first(block, "RRULE")
        recurrence_id_item = property_first(block, "RECURRENCE-ID")
        categories = [decode_ics_value(value) for _, value in block.get("CATEGORIES", [])]
        event_tags = sorted({clean_text(tag) for tag in [*tags, *categories] if clean_text(tag)})
        exdates = {
            parse_ics_datetime(value, params, default_timezone=default_timezone)
            for params, values in block.get("EXDATE", [])
            for value in values.split(",")
        }
        occurrences = [start]
        recurrence_identity: datetime | None = None
        if recurrence_item and recurrence_id_item is None:
            try:
                occurrences = list(rrulestr(recurrence_item[1], dtstart=start).between(window_start, window_end, inc=True))
            except (TypeError, ValueError, OverflowError):
                occurrences = [start]
        if recurrence_id_item:
            recurrence_identity = parse_ics_datetime(recurrence_id_item[1], recurrence_id_item[0], default_timezone=default_timezone)
            occurrences = [start]

        for occurrence in occurrences:
            occurrence = occurrence.astimezone(UTC)
            if occurrence in exdates or not window_start <= occurrence <= window_end:
                continue
            event_url = clean_text(url_item[1]) if url_item else source_page
            starts_at = utc_text(occurrence)
            identity_time = recurrence_identity or occurrence
            suffix = f":{utc_text(identity_time)}" if recurrence_item or recurrence_id_item else ""
            source_id = stable_source_id(source_name, f"{uid}{suffix}" if uid else None, title, starts_at, event_url)
            event = {
                "source_id": source_id,
                "title": clean_text(title),
                "starts_at": starts_at,
                "ends_at": utc_text(occurrence + duration) if duration else None,
                "organizer": organizer_from_ics(block),
                "location": decode_ics_value(location_item[1]) if location_item else None,
                "description": decode_ics_value(description_item[1]) if description_item else None,
                "url": event_url or None,
                "status": "cancelled" if status_item and status_item[1].upper() == "CANCELLED" else "scheduled",
                "source": source_name,
                "fetched_at": fetched_at,
                "tags": event_tags,
                "confidence": 1.0,
                "review_required": False,
            }
            output[source_id] = {key: value for key, value in event.items() if value is not None}
            if len(output) >= max_events:
                break
        if len(output) >= max_events:
            break
    return sorted(output.values(), key=lambda row: (row["starts_at"], row["title"]))


class JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.capture = False
        self.chunks: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.casefold(): value or "" for key, value in attrs}
        if tag.casefold() == "script" and attributes.get("type", "").split(";", 1)[0].strip().casefold() == "application/ld+json":
            self.capture = True
            self.chunks = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self.capture:
            self.scripts.append("".join(self.chunks).strip())
            self.capture = False


def iter_json_nodes(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from iter_json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_nodes(child)


def is_event_type(value: Any) -> bool:
    if isinstance(value, str):
        return value.rsplit("/", 1)[-1].casefold().endswith("event")
    if isinstance(value, list):
        return any(is_event_type(item) for item in value)
    return False


def jsonld_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return clean_text(value.get("name") or value.get("legalName")) or None
    if isinstance(value, list):
        return next((name for item in value if (name := jsonld_name(item))), None)
    return clean_text(value) or None


def jsonld_location(value: Any) -> str | None:
    if isinstance(value, dict):
        return clean_text(value.get("name") or jsonld_name(value.get("address")) or value.get("url")) or None
    return jsonld_name(value)


def jsonld_image(value: Any, base_url: str) -> str | None:
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl")
    if isinstance(value, list):
        return next((image for item in value if (image := jsonld_image(item, base_url))), None)
    return urljoin(base_url, clean_text(value)) if clean_text(value) else None


def extract_jsonld_events(
    html_text: str,
    *,
    page_url: str,
    source_name: str,
    fetched_at: str,
    tags: Iterable[str],
    default_timezone: str,
) -> list[dict[str, Any]]:
    parser = JsonLdParser()
    parser.feed(html_text)
    rows: dict[str, dict[str, Any]] = {}
    for script in parser.scripts:
        try:
            payload = json.loads(script)
        except json.JSONDecodeError:
            continue
        for node in iter_json_nodes(payload):
            if not is_event_type(node.get("@type")):
                continue
            title = clean_text(node.get("name"))
            start_value = node.get("startDate")
            if not title or not start_value:
                continue
            try:
                starts_at = normalize_datetime(str(start_value), default_timezone=default_timezone)
                ends_at = normalize_datetime(str(node["endDate"]), default_timezone=default_timezone) if node.get("endDate") else None
            except (ValueError, TypeError, OverflowError):
                continue
            event_url = urljoin(page_url, clean_text(node.get("url") or node.get("@id") or page_url))
            source_id = stable_source_id(source_name, clean_text(node.get("@id") or node.get("identifier") or event_url), title, starts_at, event_url)
            status = clean_text(node.get("eventStatus")).casefold()
            event = {
                "source_id": source_id,
                "title": title,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "organizer": jsonld_name(node.get("organizer")),
                "location": jsonld_location(node.get("location")),
                "description": clean_text(node.get("description")) or None,
                "url": event_url,
                "image_url": jsonld_image(node.get("image"), page_url),
                "category": clean_text(node.get("eventAttendanceMode")) or None,
                "status": "cancelled" if status.endswith("eventcancelled") else "scheduled",
                "source": source_name,
                "fetched_at": fetched_at,
                "tags": sorted({clean_text(tag) for tag in tags if clean_text(tag)}),
                "confidence": 1.0,
                "review_required": False,
            }
            rows[source_id] = {key: value for key, value in event.items() if value is not None}
    return sorted(rows.values(), key=lambda row: (row["starts_at"], row["title"]))


def canonical_url(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    parts = urlsplit(text)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    query = "&".join(piece for piece in parts.query.split("&") if piece and not piece.casefold().startswith(("utm_", "ref=", "source=")))
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), parts.path.rstrip("/") or "/", query, ""))


def title_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", clean_text(value)).casefold()
    return "".join(char for char in normalized if char.isalnum())


def event_keys(event: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    if url := canonical_url(event.get("url")):
        keys.add(("url", url))
    title = title_key(event.get("title"))
    starts_at = clean_text(event.get("starts_at") or event.get("startsAt"))
    if title and starts_at:
        try:
            minute = parse_datetime(starts_at).replace(second=0, microsecond=0).isoformat()
            keys.add(("semantic", f"{title}|{minute}"))
        except (ValueError, TypeError, OverflowError):
            pass
    return keys


def deduplicate_external(events: Iterable[dict[str, Any]], existing: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    occupied = {key for row in existing for key in event_keys(row)}
    selected: list[dict[str, Any]] = []
    excluded = 0
    for event in events:
        keys = event_keys(event)
        if keys and occupied.intersection(keys):
            excluded += 1
            continue
        selected.append(event)
        occupied.update(keys)
    return sorted(selected, key=lambda row: (str(row.get("starts_at")), str(row.get("title")))), excluded


def resolve_path(config_path: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (config_path.parent.parent / path).resolve()


def ontology_urls(source: dict[str, Any], config_path: Path) -> list[str]:
    path = resolve_path(config_path, str(source.get("ontology_path", "config/event_ontology.json")))
    payload = json.loads(path.read_text(encoding="utf-8"))
    kinds = set(source.get("allowed_link_kinds") or OFFICIAL_LINK_KINDS)
    urls: list[str] = []
    for entry in payload.get("entries", []):
        for link in entry.get("official_links", []) if isinstance(entry, dict) else []:
            if not isinstance(link, dict) or link.get("kind") not in kinds:
                continue
            if not (url := canonical_url(link.get("url"))):
                continue
            if urlsplit(url).netloc.casefold().removeprefix("www.") not in BLOCKED_JSONLD_HOSTS:
                urls.append(url)
    return sorted(set(urls))


def source_urls(source: dict[str, Any], config_path: Path) -> list[str]:
    urls = [url for value in source.get("urls", []) if (url := canonical_url(value))]
    if source.get("ontology_path"):
        urls.extend(ontology_urls(source, config_path))
    return sorted(set(urls))


def source_url(source: dict[str, Any]) -> str:
    if env_name := clean_text(source.get("url_env")):
        if value := os.environ.get(env_name, "").strip():
            return value
        raise ExternalSourceError(f"{env_name} is not configured")
    if value := clean_text(source.get("url")):
        return value
    raise ExternalSourceError("source URL is not configured")


def collect_ics(client: httpx.Client, source: dict[str, Any], *, fetched_at: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
    response = client.get(source_url(source), headers=source.get("headers"))
    response.raise_for_status()
    return parse_ics_events(
        response.text,
        source_name=clean_text(source["name"]),
        fetched_at=fetched_at,
        source_page=clean_text(source.get("source_page")) or None,
        tags=source.get("tags", []),
        default_timezone=clean_text(source.get("timezone") or "Asia/Tokyo"),
        window_start=start,
        window_end=end,
        max_events=max(1, min(int(source.get("max_events", 2000)), 10000)),
    )


def collect_jsonld(client: httpx.Client, source: dict[str, Any], *, config_path: Path, fetched_at: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for url in source_urls(source, config_path)[: max(1, min(int(source.get("max_pages", 100)), 500))]:
        response = client.get(url, headers=source.get("headers"))
        response.raise_for_status()
        for event in extract_jsonld_events(
            response.text,
            page_url=url,
            source_name=clean_text(source["name"]),
            fetched_at=fetched_at,
            tags=source.get("tags", []),
            default_timezone=clean_text(source.get("timezone") or "Asia/Tokyo"),
        ):
            if start <= parse_datetime(event["starts_at"]) <= end:
                rows.append(event)
    return sorted({row["source_id"]: row for row in rows}.values(), key=lambda row: (row["starts_at"], row["title"]))


def run_collection(*, config_path: Path, output: Path, health_output: Path, timeout: float | None = None, now: datetime | None = None) -> int:
    generated_at = (now or utc_now()).astimezone(UTC).replace(microsecond=0)
    fetched_at = utc_text(generated_at)
    config = load_config(config_path)
    request_timeout = float(timeout or config.get("http", {}).get("timeout_seconds", DEFAULT_TIMEOUT))
    window = config.get("window", {})
    start = generated_at - timedelta(days=int(window.get("past_days", 1)))
    end = generated_at + timedelta(days=int(window.get("future_days", 120)))
    previous = read_json_array(output)
    gathered: list[dict[str, Any]] = []
    results: list[SourceResult] = []

    with httpx.Client(timeout=request_timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for source in config.get("sources", []):
            if not isinstance(source, dict) or not source.get("enabled", True):
                continue
            name = clean_text(source.get("name"))
            source_type = clean_text(source.get("type"))
            source_page = clean_text(source.get("source_page")) or None
            policy_url = clean_text(source.get("policy_url")) or None
            if not name:
                raise ValueError("external source has no name")
            effective_type = source_type
            if source_type == "permissioned_ics":
                approval_env = clean_text(source.get("approval_env"))
                if not approval_env or not env_truthy(approval_env):
                    results.append(SourceResult(name, source_type, "skipped", 0, error=f"{approval_env or 'approval env'} is not approved", source_page=source_page, policy_url=policy_url))
                    continue
                effective_type = "ics"
            try:
                if effective_type == "ics":
                    events = collect_ics(client, source, fetched_at=fetched_at, start=start, end=end)
                elif effective_type in {"jsonld_pages", "ontology_jsonld"}:
                    if not source_urls(source, config_path):
                        results.append(SourceResult(name, source_type, "skipped", 0, error="no official event pages configured", source_page=source_page, policy_url=policy_url))
                        continue
                    events = collect_jsonld(client, source, config_path=config_path, fetched_at=fetched_at, start=start, end=end)
                else:
                    raise ExternalSourceError(f"unsupported external source type: {source_type}")
                gathered.extend(events)
                results.append(SourceResult(name, source_type, "ok", len(events), source_page=source_page, policy_url=policy_url))
            except Exception as exc:
                cached = [row for row in previous if clean_text(row.get("source")) == name]
                gathered.extend(cached)
                results.append(SourceResult(name, source_type, "degraded", len(cached), error=f"{type(exc).__name__}: {exc}", stale_cache_count=len(cached), source_page=source_page, policy_url=policy_url))

    existing: list[dict[str, Any]] = []
    for path in config.get("dedupe_against", []):
        existing.extend(read_json_array(resolve_path(config_path, str(path))))
    events, excluded = deduplicate_external(gathered, existing)
    write_json_atomic(output, events)
    failed = sum(result.status == "degraded" for result in results)
    succeeded = sum(result.status == "ok" for result in results)
    status = "degraded" if failed else "ok" if succeeded else "skipped"
    write_json_atomic(
        health_output,
        {
            "schema_version": "1.0",
            "generated_at": fetched_at,
            "status": status,
            "event_count": len(events),
            "deduplicated_against_existing": excluded,
            "sources": [result.as_dict() for result in results],
        },
    )
    print(f"collected {len(events)} external events ({excluded} duplicates excluded, status={status})")
    return 0


def google_public_ics_url(calendar_id: str) -> str:
    identifier = clean_text(calendar_id)
    if not identifier:
        raise ValueError("calendar_id must not be empty")
    return f"https://calendar.google.com/calendar/ical/{quote(identifier, safe='')}/public/basic.ics"


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect authorized external calendars and official event pages")
    parser.add_argument("--config", type=Path, default=Path("config/external_calendars.yaml"))
    parser.add_argument("--output", type=Path, default=Path("data/external_events.json"))
    parser.add_argument("--health-output", type=Path, default=Path("data/external_discovery_health.json"))
    parser.add_argument("--timeout", type=float)
    args = parser.parse_args()
    return run_collection(config_path=args.config, output=args.output, health_output=args.health_output, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
