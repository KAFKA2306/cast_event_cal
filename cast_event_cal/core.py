from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import httpx
import yaml
from dateutil import parser as date_parser
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
USER_AGENT = "cast-event-cal/2.0 (+https://github.com/KAFKA2306/cast_event_cal)"
DEFAULT_TIMEOUT = 25.0


class SourceError(RuntimeError):
    pass


@dataclass(slots=True)
class Event:
    id: str
    title: str
    starts_at: str
    ends_at: str | None = None
    organizer: str | None = None
    location: str | None = None
    description: str | None = None
    url: str | None = None
    image_url: str | None = None
    category: str | None = None
    status: str = "scheduled"
    source: str = "unknown"
    source_id: str | None = None
    fetched_at: str | None = None
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    review_required: bool = False

    def normalized(self) -> "Event":
        self.title = clean_text(self.title)
        self.organizer = clean_optional(self.organizer)
        self.location = clean_optional(self.location)
        self.description = clean_optional(self.description)
        self.url = clean_optional(self.url)
        self.image_url = clean_optional(self.image_url)
        self.category = clean_optional(self.category)
        self.tags = sorted({clean_text(tag) for tag in self.tags if clean_text(tag)})
        self.starts_at = normalize_datetime(self.starts_at)
        self.ends_at = normalize_datetime(self.ends_at) if self.ends_at else None
        if self.ends_at and parse_datetime(self.ends_at) < parse_datetime(self.starts_at):
            self.review_required = True
            self.confidence = min(self.confidence, 0.3)
        return self

    @property
    def start(self) -> datetime:
        return parse_datetime(self.starts_at)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_optional(value: Any) -> str | None:
    cleaned = clean_text(value)
    return cleaned or None


def parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = date_parser.isoparse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(UTC)


def normalize_datetime(value: str | datetime) -> str:
    return parse_datetime(value).isoformat().replace("+00:00", "Z")


def event_identity(*, source: str, source_id: str | None, title: str, starts_at: str, organizer: str | None, location: str | None) -> str:
    if source_id:
        payload = f"{source}:{source_id}"
    else:
        payload = "|".join(
            [
                clean_text(organizer).casefold(),
                clean_text(title).casefold(),
                normalize_datetime(starts_at),
                clean_text(location).casefold(),
            ]
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def build_event(raw: dict[str, Any], source: str, fetched_at: str) -> Event:
    source_id = clean_optional(raw.get("source_id") or raw.get("id") or raw.get("uid"))
    starts_at = raw.get("starts_at") or raw.get("start") or raw.get("start_time") or raw.get("startsAt")
    if not starts_at:
        raise ValueError("event has no start time")
    title = clean_text(raw.get("title") or raw.get("name"))
    if not title:
        raise ValueError("event has no title")
    organizer_value = raw.get("organizer") or raw.get("host") or raw.get("owner")
    organizer = organizer_value.get("name") if isinstance(organizer_value, dict) else organizer_value
    location_value = raw.get("location") or raw.get("venue") or raw.get("world")
    location = location_value.get("name") if isinstance(location_value, dict) else location_value
    event = Event(
        id=event_identity(
            source=source,
            source_id=source_id,
            title=title,
            starts_at=str(starts_at),
            organizer=clean_optional(organizer),
            location=clean_optional(location),
        ),
        title=title,
        starts_at=str(starts_at),
        ends_at=raw.get("ends_at") or raw.get("end") or raw.get("end_time") or raw.get("endsAt"),
        organizer=clean_optional(organizer),
        location=clean_optional(location),
        description=raw.get("description") or raw.get("text"),
        url=raw.get("url") or raw.get("event_url"),
        image_url=raw.get("image_url") or raw.get("imageUrl"),
        category=raw.get("category"),
        status=clean_text(raw.get("status") or "scheduled").lower(),
        source=source,
        source_id=source_id,
        fetched_at=fetched_at,
        tags=list(raw.get("tags") or []),
        confidence=float(raw.get("confidence", 1.0)),
        review_required=bool(raw.get("review_required", False)),
    )
    return event.normalized()


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise ValueError("configuration root must be a mapping")
    return config


def fetch_json(client: httpx.Client, url: str, *, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None) -> Any:
    response = client.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def collect_json_source(client: httpx.Client, source: dict[str, Any], fetched_at: str) -> list[Event]:
    data = fetch_json(client, str(source["url"]), headers=source.get("headers"))
    path = source.get("items_path", "")
    for key in [piece for piece in str(path).split(".") if piece]:
        if not isinstance(data, dict) or key not in data:
            raise SourceError(f"items_path not found: {path}")
        data = data[key]
    if not isinstance(data, list):
        raise SourceError("JSON source did not return an event array")
    return [build_event(item, source["name"], fetched_at) for item in data if isinstance(item, dict)]


def unfold_ics(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def decode_ics_value(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def parse_ics_datetime(key: str, value: str) -> str:
    params = key.split(";")[1:]
    tzid = next((p.split("=", 1)[1] for p in params if p.startswith("TZID=")), None)
    date_only = any(p == "VALUE=DATE" for p in params)
    if date_only or re.fullmatch(r"\d{8}", value):
        dt = datetime.strptime(value[:8], "%Y%m%d").replace(tzinfo=ZoneInfo(tzid) if tzid else JST)
    elif value.endswith("Z"):
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    else:
        fmt = "%Y%m%dT%H%M%S" if len(value) >= 15 else "%Y%m%dT%H%M"
        dt = datetime.strptime(value, fmt).replace(tzinfo=ZoneInfo(tzid) if tzid else JST)
    return normalize_datetime(dt)


def parse_ics(text: str, source_name: str, fetched_at: str) -> list[Event]:
    events: list[Event] = []
    current: dict[str, str] | None = None
    for line in unfold_ics(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT" and current is not None:
            try:
                raw = {
                    "source_id": current.get("UID"),
                    "title": decode_ics_value(current.get("SUMMARY", "")),
                    "starts_at": current["DTSTART"],
                    "ends_at": current.get("DTEND"),
                    "description": decode_ics_value(current.get("DESCRIPTION", "")),
                    "location": decode_ics_value(current.get("LOCATION", "")),
                    "url": current.get("URL"),
                    "status": current.get("STATUS", "scheduled").lower(),
                }
                events.append(build_event(raw, source_name, fetched_at))
            except (KeyError, ValueError):
                pass
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        base_key = key.split(";", 1)[0].upper()
        if base_key in {"DTSTART", "DTEND"}:
            current[base_key] = parse_ics_datetime(key, value)
        elif base_key in {"UID", "SUMMARY", "DESCRIPTION", "LOCATION", "URL", "STATUS"}:
            current[base_key] = value
    return events


def collect_ics_source(client: httpx.Client, source: dict[str, Any], fetched_at: str) -> list[Event]:
    response = client.get(str(source["url"]), headers=source.get("headers"))
    response.raise_for_status()
    return parse_ics(response.text, source["name"], fetched_at)


def collect_manual_source(source: dict[str, Any], config_dir: Path, fetched_at: str) -> list[Event]:
    path = Path(source["path"])
    if not path.is_absolute():
        path = (config_dir.parent / path).resolve()
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise SourceError("manual source must contain a JSON array")
    return [build_event(item, source["name"], fetched_at) for item in data if isinstance(item, dict)]


def x_headers() -> dict[str, str]:
    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    if not token:
        raise SourceError("X_BEARER_TOKEN is not configured")
    return {"Authorization": f"Bearer {token}"}


def x_post_to_event(post: dict[str, Any], users: dict[str, str], source_name: str, fetched_at: str) -> Event | None:
    text = clean_text(post.get("text"))
    created_at = post.get("created_at")
    if not text or not created_at:
        return None
    created = parse_datetime(str(created_at)).astimezone(JST)
    date_match = re.search(r"(?:(\d{4})[./年-])?(\d{1,2})[./月-](\d{1,2})日?", text)
    time_match = re.search(r"(?<!\d)([01]?\d|2[0-3])[:時](\d{2})?", text)
    if not date_match or not time_match:
        return None
    year = int(date_match.group(1) or created.year)
    month = int(date_match.group(2))
    day = int(date_match.group(3))
    hour = int(time_match.group(1))
    minute = int(time_match.group(2) or 0)
    try:
        start = datetime(year, month, day, hour, minute, tzinfo=JST)
    except ValueError:
        return None
    if not date_match.group(1) and start < created - timedelta(days=45):
        start = start.replace(year=start.year + 1)
    author_id = str(post.get("author_id") or "")
    username = users.get(author_id)
    post_id = str(post.get("id"))
    title = text[:72] + ("…" if len(text) > 72 else "")
    raw = {
        "source_id": post_id,
        "title": title,
        "starts_at": start,
        "organizer": f"@{username}" if username else None,
        "description": text,
        "url": f"https://x.com/{username}/status/{post_id}" if username else f"https://x.com/i/web/status/{post_id}",
        "tags": ["X", "自動抽出"],
        "confidence": 0.72,
        "review_required": False,
    }
    return build_event(raw, source_name, fetched_at)


def collect_x_source(client: httpx.Client, source: dict[str, Any], fetched_at: str) -> list[Event]:
    kind = source["type"]
    if kind == "x_recent_search":
        endpoint = "https://api.x.com/2/tweets/search/recent"
        params: dict[str, Any] = {"query": source["query"], "max_results": min(int(source.get("max_results", 100)), 100)}
    elif kind == "x_list":
        endpoint = f"https://api.x.com/2/lists/{source['list_id']}/tweets"
        params = {"max_results": min(int(source.get("max_results", 100)), 100)}
    else:
        raise SourceError(f"unsupported X source: {kind}")
    params.update({"tweet.fields": "created_at,author_id", "expansions": "author_id", "user.fields": "username"})
    payload = fetch_json(client, endpoint, headers=x_headers(), params=params)
    users = {str(item["id"]): str(item["username"]) for item in payload.get("includes", {}).get("users", []) if item.get("id") and item.get("username")}
    events: list[Event] = []
    for post in payload.get("data", []):
        event = x_post_to_event(post, users, source["name"], fetched_at)
        if event:
            events.append(event)
    return events


def collect_vrchat_group_source(client: httpx.Client, source: dict[str, Any], fetched_at: str) -> list[Event]:
    cookie = os.environ.get("VRCHAT_AUTH_COOKIE", "").strip()
    if not cookie:
        raise SourceError("VRCHAT_AUTH_COOKIE is not configured")
    group_id = clean_text(source.get("group_id"))
    if not re.fullmatch(r"grp_[0-9a-fA-F-]{36}", group_id):
        raise SourceError("invalid VRChat group_id")
    headers = {"Cookie": f"auth={cookie}"}
    params = {"n": min(int(source.get("max_results", 100)), 100), "offset": 0}
    payload = fetch_json(client, f"https://api.vrchat.cloud/api/1/calendar/{group_id}", headers=headers, params=params)
    rows = payload.get("results", payload if isinstance(payload, list) else [])
    events: list[Event] = []
    for item in rows:
        if not isinstance(item, dict) or item.get("isDraft"):
            continue
        raw = {
            "source_id": item.get("id"),
            "title": item.get("title"),
            "starts_at": item.get("startsAt"),
            "ends_at": item.get("endsAt"),
            "description": item.get("description"),
            "image_url": item.get("imageUrl"),
            "category": item.get("category"),
            "status": "cancelled" if item.get("deletedAt") else "scheduled",
            "location": item.get("accessType"),
            "tags": list(item.get("tags") or []) + list(item.get("languages") or []),
            "url": f"https://vrchat.com/home/group/{group_id}",
        }
        events.append(build_event(raw, source["name"], fetched_at))
    return events


def collect_source(client: httpx.Client, source: dict[str, Any], config_dir: Path, fetched_at: str) -> list[Event]:
    source_type = clean_text(source.get("type"))
    if source_type == "manual_json":
        return collect_manual_source(source, config_dir, fetched_at)
    if source_type == "json":
        return collect_json_source(client, source, fetched_at)
    if source_type == "ics":
        return collect_ics_source(client, source, fetched_at)
    if source_type in {"x_recent_search", "x_list"}:
        return collect_x_source(client, source, fetched_at)
    if source_type == "vrchat_group":
        return collect_vrchat_group_source(client, source, fetched_at)
    raise SourceError(f"unsupported source type: {source_type}")


def deduplicate(events: Iterable[Event]) -> list[Event]:
    selected: dict[str, Event] = {}
    for event in events:
        current = selected.get(event.id)
        if current is None:
            selected[event.id] = event
            continue
        current_updated = parse_datetime(current.fetched_at or "1970-01-01T00:00:00Z")
        candidate_updated = parse_datetime(event.fetched_at or "1970-01-01T00:00:00Z")
        if candidate_updated >= current_updated:
            selected[event.id] = event
    return sorted(selected.values(), key=lambda item: (item.start, item.title.casefold()))


def filter_window(events: Iterable[Event], *, past_days: int, future_days: int, now: datetime | None = None) -> list[Event]:
    anchor = (now or utc_now()).astimezone(UTC)
    lower = anchor - timedelta(days=past_days)
    upper = anchor + timedelta(days=future_days)
    return [event for event in events if lower <= event.start <= upper]


def ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold_ics(line: str) -> str:
    encoded = line.encode("utf-8")
    chunks: list[bytes] = []
    while len(encoded) > 75:
        cut = 75
        while cut > 0 and (encoded[cut] & 0b11000000) == 0b10000000:
            cut -= 1
        chunks.append(encoded[:cut])
        encoded = encoded[cut:]
    chunks.append(encoded)
    return "\r\n ".join(chunk.decode("utf-8") for chunk in chunks)


def render_ics(events: Iterable[Event], generated_at: datetime) -> str:
    stamp = generated_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//KAFKA2306//cast_event_cal//JA",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:VRChat Event Calendar",
        "X-WR-TIMEZONE:Asia/Tokyo",
    ]
    for event in events:
        lines.extend(["BEGIN:VEVENT", f"UID:{event.id}@cast-event-cal", f"DTSTAMP:{stamp}"])
        lines.append(f"DTSTART:{event.start.strftime('%Y%m%dT%H%M%SZ')}")
        if event.ends_at:
            lines.append(f"DTEND:{parse_datetime(event.ends_at).strftime('%Y%m%dT%H%M%SZ')}")
        lines.append(f"SUMMARY:{ics_escape(event.title)}")
        if event.description:
            lines.append(f"DESCRIPTION:{ics_escape(event.description)}")
        if event.location:
            lines.append(f"LOCATION:{ics_escape(event.location)}")
        if event.url:
            lines.append(f"URL:{event.url}")
        if event.status == "cancelled":
            lines.append("STATUS:CANCELLED")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_ics(line) for line in lines) + "\r\n"


def render_index(generated_at: str) -> str:
    return f"""<!doctype html>
<html lang=\"ja\">
<head>
<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<meta name=\"description\" content=\"VRChatイベントを複数の公開情報源から自動集約するカレンダー\">
<title>VRChat Event Calendar</title>
<style>
:root{{--bg:#fbfaf7;--ink:#243653;--blue:#8fb5ec;--lav:#b9a8e6;--rose:#efb4c1;--mint:#b7dbc8;--apricot:#f3cfaa;--card:#fff;--shadow:0 18px 50px rgba(76,91,125,.09)}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 8% 0%,#eef5ff,transparent 34%),var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,\"Noto Sans JP\",sans-serif}}main{{max-width:1120px;margin:auto;padding:44px 20px 72px}}header{{display:grid;gap:14px;margin-bottom:28px}}h1{{font-size:clamp(2rem,5vw,4.6rem);line-height:.95;letter-spacing:-.05em;margin:0;max-width:850px}}.lede{{font-size:1.08rem;max-width:760px;line-height:1.8}}.toolbar{{display:flex;flex-wrap:wrap;gap:10px;align-items:center}}input,select,a.button{{border:1px solid #dbe3ef;border-radius:999px;background:#fff;color:var(--ink);padding:12px 16px;font:inherit;text-decoration:none}}input{{min-width:260px;flex:1}}.status{{font-size:.9rem;opacity:.72}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-top:24px}}article{{background:var(--card);border:1px solid rgba(143,181,236,.34);border-radius:22px;padding:20px;box-shadow:var(--shadow);display:grid;gap:11px}}article.review{{border-color:var(--apricot)}}article.cancelled{{opacity:.6}}.date{{font-weight:750;color:#516b93}}h2{{font-size:1.15rem;line-height:1.45;margin:0}}.meta{{font-size:.92rem;line-height:1.55}}.tags{{display:flex;gap:6px;flex-wrap:wrap}}.tag{{font-size:.78rem;padding:4px 9px;background:#f2f5fa;border-radius:999px}}.empty{{padding:40px;border:1px dashed #b9c7dc;border-radius:22px;text-align:center}}footer{{margin-top:42px;font-size:.86rem;opacity:.7}}
</style>
</head>
<body><main><header><div class=\"status\">AUTOMATED / SOURCE-TRACEABLE / JST</div><h1>VRChat Event Calendar</h1><p class=\"lede\">公開JSON・ICS、VRChat Group Calendar、X APIから取得したイベントを、出典と時刻を保持したまま統合します。曖昧な日時は推測せず除外または要確認にします。</p><div class=\"toolbar\"><input id=\"q\" type=\"search\" placeholder=\"イベント、主催者、会場を検索\"><select id=\"range\"><option value=\"all\">すべて</option><option value=\"today\">今日</option><option value=\"week\">7日以内</option><option value=\"month\">30日以内</option></select><a class=\"button\" href=\"calendar.ics\">カレンダーを購読</a></div><div id=\"health\" class=\"status\">データ読込中</div></header><section id=\"events\" class=\"grid\"></section><footer>Generated: {html.escape(generated_at)} · <a href=\"events.json\">JSON API</a> · <a href=\"health.json\">取得状態</a> · <a href=\"https://github.com/KAFKA2306/cast_event_cal\">GitHub</a></footer></main>
<script>
const state={{events:[],health:null}};const esc=s=>String(s??'').replace(/[&<>\"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}}[c]));
const fmt=iso=>new Intl.DateTimeFormat('ja-JP',{{timeZone:'Asia/Tokyo',month:'short',day:'numeric',weekday:'short',hour:'2-digit',minute:'2-digit'}}).format(new Date(iso));
function render(){{const q=document.querySelector('#q').value.toLowerCase();const range=document.querySelector('#range').value;const now=new Date();const end=new Date(now);end.setDate(end.getDate()+(range==='today'?1:range==='week'?7:range==='month'?30:36500));const rows=state.events.filter(e=>{{const hay=[e.title,e.organizer,e.location,e.description,(e.tags||[]).join(' ')].join(' ').toLowerCase();return hay.includes(q)&&(range==='all'||(new Date(e.starts_at)>=now&&new Date(e.starts_at)<=end));}});document.querySelector('#events').innerHTML=rows.length?rows.map(e=>`<article class=\"${{e.review_required?'review ':''}}${{e.status==='cancelled'?'cancelled':''}}\"><div class=\"date\">${{fmt(e.starts_at)}}</div><h2>${{esc(e.title)}}</h2><div class=\"meta\">${{e.organizer?'主催: '+esc(e.organizer)+'<br>':''}}${{e.location?'会場: '+esc(e.location)+'<br>':''}}出典: ${{esc(e.source)}}</div><div class=\"tags\">${{(e.tags||[]).map(t=>`<span class=\"tag\">${{esc(t)}}</span>`).join('')}}</div>${{e.url?`<a href=\"${{esc(e.url)}}\" target=\"_blank\" rel=\"noopener\">告知を見る →</a>`:''}}</article>`).join(''):'<div class=\"empty\">条件に合うイベントはありません。</div>';}}
Promise.all([fetch('events.json').then(r=>r.json()),fetch('health.json').then(r=>r.json())]).then(([data,health])=>{{state.events=data.events||[];state.health=health;document.querySelector('#health').textContent=`${{state.events.length}}件 · ${{health.status}} · 最終更新 ${{fmt(health.generated_at)}}`;render();}}).catch(()=>document.querySelector('#health').textContent='データを読み込めませんでした');document.querySelector('#q').addEventListener('input',render);document.querySelector('#range').addEventListener('change',render);
</script></body></html>"""


def write_outputs(events: list[Event], health: dict[str, Any], output_dir: Path, generated_at: datetime) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "2.0",
        "generated_at": normalize_datetime(generated_at),
        "timezone": "Asia/Tokyo",
        "count": len(events),
        "events": [asdict(event) for event in events],
    }
    (output_dir / "events.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "calendar.ics").write_text(render_ics(events, generated_at), encoding="utf-8", newline="")
    (output_dir / "health.json").write_text(json.dumps(health, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "index.html").write_text(render_index(payload["generated_at"]), encoding="utf-8")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")


def run(config_path: Path, output_dir: Path, *, strict: bool = False) -> int:
    generated_at = utc_now()
    fetched_at = normalize_datetime(generated_at)
    config = load_config(config_path)
    sources = config.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources must be a list")
    timeout = float(config.get("http", {}).get("timeout_seconds", DEFAULT_TIMEOUT))
    all_events: list[Event] = []
    source_results: list[dict[str, Any]] = []
    enabled_count = 0
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for source in sources:
            if not isinstance(source, dict) or not source.get("enabled", True):
                continue
            enabled_count += 1
            name = clean_text(source.get("name") or source.get("type") or "unnamed")
            started = utc_now()
            try:
                events = collect_source(client, source, config_path.parent, fetched_at)
                all_events.extend(events)
                source_results.append({"name": name, "status": "ok", "count": len(events), "duration_ms": int((utc_now() - started).total_seconds() * 1000)})
            except Exception as exc:
                logging.exception("source failed: %s", name)
                source_results.append({"name": name, "status": "error", "count": 0, "error": f"{type(exc).__name__}: {exc}", "duration_ms": int((utc_now() - started).total_seconds() * 1000)})
    events = deduplicate(all_events)
    window = config.get("window", {})
    events = filter_window(events, past_days=int(window.get("past_days", 1)), future_days=int(window.get("future_days", 120)), now=generated_at)
    failed = sum(item["status"] == "error" for item in source_results)
    succeeded = sum(item["status"] == "ok" for item in source_results)
    status = "ok" if failed == 0 else "degraded" if succeeded > 0 else "error"
    health = {
        "schema_version": "1.0",
        "generated_at": fetched_at,
        "status": status,
        "enabled_sources": enabled_count,
        "successful_sources": succeeded,
        "failed_sources": failed,
        "event_count": len(events),
        "sources": source_results,
    }
    write_outputs(events, health, output_dir, generated_at)
    if strict and failed:
        return 2
    if enabled_count and succeeded == 0:
        return 1
    return 0


def validate(config_path: Path) -> int:
    config = load_config(config_path)
    errors: list[str] = []
    names: set[str] = set()
    for index, source in enumerate(config.get("sources", [])):
        if not isinstance(source, dict):
            errors.append(f"sources[{index}] must be a mapping")
            continue
        name = clean_text(source.get("name"))
        if not name:
            errors.append(f"sources[{index}] has no name")
        elif name in names:
            errors.append(f"duplicate source name: {name}")
        names.add(name)
        if source.get("type") not in {"manual_json", "json", "ics", "x_recent_search", "x_list", "vrchat_group"}:
            errors.append(f"unsupported source type at sources[{index}]: {source.get('type')}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"configuration ok: {len(names)} sources")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VRChat event calendar automation")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="collect, normalize, deduplicate and publish")
    run_parser.add_argument("--config", type=Path, default=Path("config/sources.yaml"))
    run_parser.add_argument("--output", type=Path, default=Path("public"))
    run_parser.add_argument("--strict", action="store_true")
    validate_parser = sub.add_parser("validate", help="validate source configuration")
    validate_parser.add_argument("--config", type=Path, default=Path("config/sources.yaml"))
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        return validate(args.config)
    return run(args.config, args.output, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
