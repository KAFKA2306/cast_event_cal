from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo

import httpx

JST = ZoneInfo("Asia/Tokyo")
OUTPUT_PATH = Path("data/yahoo_realtime_events.json")
REJECTED_PATH = Path("data/yahoo_realtime_rejected.json")
HEALTH_PATH = Path("data/yahoo_realtime_health.json")
X_EVENTS_PATH = Path("data/x_events.json")
DEFAULT_QUERY = (
    '(イベント OR 参加方法 OR 参加条件 OR 開催 OR 主催 OR join OR ジョイン OR リクイン OR reqin '
    'OR リクエストインバイト OR "request invite" OR 本日 OR 営業 OR 応募) (VRChat OR VRC)'
)
DEFAULT_SEARCH_URL = "https://search.yahoo.co.jp/realtime/search?" + urlencode(
    {"ei": "UTF-8", "p": DEFAULT_QUERY, "md": "h"}
)
PARSER_VERSION = "1.0"
STATUS_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:x|twitter)\.com/[^\s\"'<>\\]+/status/(\d+)", re.IGNORECASE
)
STATUS_ID_RE = re.compile(r"\b\d{10,25}\b")
VRCHAT_RE = re.compile(r"(?i)(?:#?vrchat|#?vrc\b)")
EVENT_TERMS = {
    "イベント", "参加方法", "参加条件", "開催", "主催", "join", "ジョイン", "リクイン",
    "reqin", "リクエストインバイト", "request invite", "本日", "営業", "公演", "集会",
    "ライブ", "ツアー", "開場",
}
RECRUITMENT_TERMS = {"募集", "応募", "締切", "〆切", "テスター"}
PRODUCT_TERMS = {
    "booth", "販売開始", "発売", "プレゼント企画", "giveaway", "rpキャンペーン",
    "プレゼントキャンペーン", "無料配布",
}
RETWEET_KEYS = {
    "retweet_count", "retweetcount", "retweets", "repost_count", "repostcount", "reposts", "rtcount",
}
TEXT_KEYS = ("full_text", "fullText", "tweetText", "text", "content", "body", "description")
URL_KEYS = ("tweetUrl", "statusUrl", "permalink", "url", "link", "href")
ID_KEYS = ("tweetId", "statusId", "id_str", "rest_id", "id")
AUTHOR_KEYS = ("screen_name", "screenName", "username", "userName", "handle")
CREATED_KEYS = ("created_at", "createdAt", "timestamp", "date", "publishedAt")


class JsonScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capturing = False
        self._parts: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attributes = {key.lower(): value or "" for key, value in attrs}
        script_type = attributes.get("type", "").lower()
        script_id = attributes.get("id", "").lower()
        if "json" in script_type or script_id in {"__next_data__", "__initial_state__"}:
            self._capturing = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capturing:
            self.scripts.append("".join(self._parts).strip())
            self._capturing = False
            self._parts = []


def utc_text(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_instant(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    return parsed.astimezone(UTC)


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def first_string(mapping: dict[str, Any], keys: Iterable[str]) -> str | None:
    lowered = {str(key).casefold(): value for key, value in mapping.items()}
    for key in keys:
        value = lowered.get(key.casefold())
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def find_text(mapping: dict[str, Any]) -> str | None:
    for node in walk(mapping):
        if not isinstance(node, dict):
            continue
        text = first_string(node, TEXT_KEYS)
        if text and len(text) >= 8:
            return text
    return None


def status_id_from_mapping(mapping: dict[str, Any]) -> str | None:
    for value in walk(mapping):
        if not isinstance(value, str):
            continue
        match = STATUS_RE.search(value.replace("\\/", "/"))
        if match:
            return match.group(1)
    for key in ID_KEYS:
        value = mapping.get(key)
        text = str(value).strip() if isinstance(value, (int, str)) else ""
        if STATUS_ID_RE.fullmatch(text):
            return text
    return None


def status_url_from_mapping(mapping: dict[str, Any], status_id: str) -> str:
    for value in walk(mapping):
        if not isinstance(value, str):
            continue
        normalized = value.replace("\\/", "/")
        if STATUS_RE.search(normalized):
            return normalized if normalized.startswith("http") else f"https://{normalized.lstrip('/')}"
    return f"https://x.com/i/web/status/{status_id}"


def find_retweet_count(mapping: dict[str, Any]) -> int | None:
    for node in walk(mapping):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if str(key).casefold().replace("-", "_") not in RETWEET_KEYS or isinstance(value, bool):
                continue
            try:
                return int(str(value).replace(",", ""))
            except ValueError:
                continue
    return None


def find_nested_string(mapping: dict[str, Any], keys: Iterable[str]) -> str | None:
    for node in walk(mapping):
        if isinstance(node, dict) and (value := first_string(node, keys)):
            return value
    return None


def candidate_from_mapping(mapping: dict[str, Any]) -> dict[str, Any] | None:
    text = find_text(mapping)
    status_id = status_id_from_mapping(mapping)
    if not text or not status_id:
        return None
    author = find_nested_string(mapping, AUTHOR_KEYS)
    return {
        "status_id": status_id,
        "url": status_url_from_mapping(mapping, status_id),
        "text": unescape(text),
        "author": author.lstrip("@") if author else None,
        "created_at": find_nested_string(mapping, CREATED_KEYS),
        "retweet_count": find_retweet_count(mapping),
    }


def extract_json_payloads(html_text: str) -> list[Any]:
    collector = JsonScriptCollector()
    collector.feed(html_text)
    payloads: list[Any] = []
    for raw in collector.scripts:
        try:
            payloads.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return payloads


def strip_html(value: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def fallback_candidates(html_text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    normalized_html = html_text.replace("\\/", "/")
    for match in STATUS_RE.finditer(normalized_html):
        status_id = match.group(1)
        window = normalized_html[max(0, match.start() - 2500) : min(len(normalized_html), match.end() + 2500)]
        retweet_match = re.search(
            r"(?i)(?:retweet_count|retweetCount|repost_count|repostCount|rtCount)[\"'\s:=]+([\d,]+)",
            window,
        )
        candidates.append(
            {
                "status_id": status_id,
                "url": f"https://x.com/i/web/status/{status_id}",
                "text": strip_html(window)[:2000],
                "author": None,
                "created_at": None,
                "retweet_count": int(retweet_match.group(1).replace(",", "")) if retweet_match else None,
            }
        )
    return candidates


def extract_candidates(html_text: str) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for payload in extract_json_payloads(html_text):
        for node in walk(payload):
            if not isinstance(node, dict) or (candidate := candidate_from_mapping(node)) is None:
                continue
            status_id = str(candidate["status_id"])
            current = selected.get(status_id)
            current_score = (
                len(str(current.get("text", ""))) + (10000 if current.get("retweet_count") is not None else 0)
                if current else 0
            )
            candidate_score = len(str(candidate.get("text", ""))) + (
                10000 if candidate.get("retweet_count") is not None else 0
            )
            if current is None or candidate_score > current_score:
                selected[status_id] = candidate
    for candidate in fallback_candidates(html_text):
        selected.setdefault(str(candidate["status_id"]), candidate)
    return list(selected.values())


def normalize_text(text: str) -> str:
    return (
        text.replace("：", ":").replace("／", "/").replace("．", ".").replace("－", "-")
        .replace("〜", "~").replace("～", "~")
    )


def parse_event_datetime(text: str, anchor: datetime) -> datetime | None:
    normalized = normalize_text(text)
    time_part = r"(?P<hour>[01]?\d|2[0-3])(?:[:時](?P<minute>\d{2})?)"
    date_patterns = [
        rf"(?P<year>20\d{{2}})[./年-](?P<month>\d{{1,2}})[./月-](?P<day>\d{{1,2}})日?"
        rf"(?:\s*[（(]?[月火水木金土日][）)]?)?.{{0,40}}?{time_part}",
        rf"(?P<month>\d{{1,2}})[./月-](?P<day>\d{{1,2}})日?"
        rf"(?:\s*[（(]?[月火水木金土日][）)]?)?.{{0,40}}?{time_part}",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        groups = match.groupdict()
        try:
            candidate = datetime(
                int(groups.get("year") or anchor.year), int(groups["month"]), int(groups["day"]),
                int(groups["hour"]), int(groups.get("minute") or 0), tzinfo=JST,
            )
        except ValueError:
            return None
        if not groups.get("year") and candidate < anchor - timedelta(days=2):
            try:
                candidate = candidate.replace(year=candidate.year + 1)
            except ValueError:
                return None
        return candidate
    relative_match = re.search(
        rf"(?P<day>本日|今日|明日).{{0,30}}?{time_part}", normalized, flags=re.IGNORECASE | re.DOTALL
    )
    if not relative_match:
        return None
    local_day = (anchor + timedelta(days=1 if relative_match.group("day") == "明日" else 0)).date()
    return datetime(
        local_day.year, local_day.month, local_day.day, int(relative_match.group("hour")),
        int(relative_match.group("minute") or 0), tzinfo=JST,
    )


def classify(text: str) -> tuple[str | None, str | None]:
    lowered = text.casefold()
    if not VRCHAT_RE.search(text):
        return None, "not_vrchat"
    has_event = any(term in lowered for term in EVENT_TERMS)
    has_recruitment = any(term in lowered for term in RECRUITMENT_TERMS)
    has_product = any(term in lowered for term in PRODUCT_TERMS)
    if has_product and not has_event and not has_recruitment:
        return None, "product_only"
    if has_recruitment and any(term in lowered for term in ("締切", "〆切", "応募", "テスター")):
        return "recruitment_deadline", None
    if has_event:
        return "event", None
    return None, "missing_event_marker"


def title_from_text(text: str, category: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line and not line.startswith("http")]
    if category == "recruitment_deadline":
        selected = next((line for line in lines if any(term in line for term in RECRUITMENT_TERMS)), None)
    else:
        selected = next(
            (line.strip("『』「」【】") for line in lines if line.startswith(("『", "「", "【")) and line.endswith(("』", "」", "】"))),
            None,
        )
        selected = selected or next(
            (line for line in lines if VRCHAT_RE.search(line) or any(term in line.casefold() for term in EVENT_TERMS)),
            None,
        )
    selected = selected or (lines[0] if lines else "VRChatイベント")
    return selected[:96] + ("…" if len(selected) > 96 else "")


def x_status_ids(events: Iterable[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for event in events:
        source_id = str(event.get("source_id") or "")
        if source_id.startswith("x:"):
            result.add(source_id.split(":", 1)[1])
        if match := STATUS_RE.search(str(event.get("url") or "")):
            result.add(match.group(1))
    return result


def candidate_to_event(
    candidate: dict[str, Any], *, now: datetime, min_retweets: int, known_x_ids: set[str]
) -> tuple[dict[str, Any] | None, str | None]:
    status_id = str(candidate.get("status_id") or "")
    text = str(candidate.get("text") or "").strip()
    if not STATUS_ID_RE.fullmatch(status_id):
        return None, "invalid_status_id"
    if status_id in known_x_ids:
        return None, "duplicate_x_source"
    if len(text) < 12:
        return None, "missing_text"
    category, rejection = classify(text)
    if rejection:
        return None, rejection
    retweet_count = candidate.get("retweet_count")
    if retweet_count is None:
        return None, "retweet_count_missing"
    try:
        retweet_count = int(retweet_count)
    except (TypeError, ValueError):
        return None, "retweet_count_invalid"
    if retweet_count < min_retweets:
        return None, "retweet_below_threshold"
    event_at = parse_event_datetime(text, now.astimezone(JST))
    if event_at is None:
        return None, "missing_datetime"
    if event_at < now.astimezone(JST) - timedelta(hours=12):
        return None, "past_event"
    if event_at > now.astimezone(JST) + timedelta(days=180):
        return None, "too_far_future"
    author = str(candidate.get("author") or "").strip().lstrip("@")
    url = str(candidate.get("url") or f"https://x.com/i/web/status/{status_id}")
    if not STATUS_RE.search(url):
        url = f"https://x.com/i/web/status/{status_id}"
    event = {
        "source_id": f"yahoo:x:{status_id}",
        "title": title_from_text(text, str(category)),
        "starts_at": utc_text(event_at),
        "organizer": f"@{author}" if author else None,
        "location": "オンライン" if category == "recruitment_deadline" else "VRChat",
        "description": re.sub(r"\s+", " ", text).strip()[:1800],
        "url": url,
        "category": category,
        "tags": ["VRChat", "Yahoo!リアルタイム検索", "機械判定", "リポスト3件以上"],
        "confidence": 0.88,
        "review_required": False,
    }
    return {key: value for key, value in event.items() if value is not None}, None


def merge_cache(existing: list[dict[str, Any]], fresh: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    lower, upper = now - timedelta(days=1), now + timedelta(days=180)
    selected: dict[str, dict[str, Any]] = {}
    for event in existing + fresh:
        start = parse_instant(str(event.get("starts_at") or ""))
        source_id = str(event.get("source_id") or "")
        if start is not None and source_id and lower <= start <= upper:
            selected[source_id] = event
    return sorted(selected.values(), key=lambda item: (str(item.get("starts_at")), str(item.get("title"))))


def validate_search_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "search.yahoo.co.jp" or parsed.path != "/realtime/search":
        raise ValueError("Yahoo realtime URL must use https://search.yahoo.co.jp/realtime/search")


def fetch_page(url: str) -> tuple[str, int, str]:
    headers = {
        "User-Agent": "cast-event-cal/3.0 (+https://github.com/KAFKA2306/cast_event_cal)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja,en-US;q=0.7,en;q=0.4",
    }
    errors: list[str] = []
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
                response = client.get(url)
                response.raise_for_status()
                final_url = str(response.url)
                if urlparse(final_url).hostname not in {"search.yahoo.co.jp", "search.yahoo.com"}:
                    raise RuntimeError(f"unexpected redirect host: {final_url}")
                content_type = response.headers.get("content-type", "")
                if "html" not in content_type.casefold():
                    raise RuntimeError(f"unexpected content type: {content_type}")
                if len(response.text) < 5000:
                    raise RuntimeError(f"response too small: {len(response.text)} bytes")
                return response.text, response.status_code, final_url
        except (httpx.HTTPError, RuntimeError) as exc:
            errors.append(str(exc))
            if attempt < 2:
                time.sleep(2**attempt)
    raise RuntimeError("; ".join(errors))


def write_health(
    *, status: str, reason: str | None, search_url: str, http_status: int | None,
    final_url: str | None, html_bytes: int, fetched_candidates: int, accepted_candidates: int,
    rejected_candidates: int, retained_events: int, event_count: int, rejection_counts: Counter[str],
) -> None:
    atomic_write_json(
        HEALTH_PATH,
        {
            "schema_version": "1.0", "parser_version": PARSER_VERSION,
            "generated_at": utc_text(datetime.now(UTC)), "status": status, "reason": reason,
            "search_url": search_url, "http_status": http_status, "final_url": final_url,
            "html_bytes": html_bytes, "fetched_candidates": fetched_candidates,
            "accepted_candidates": accepted_candidates, "rejected_candidates": rejected_candidates,
            "retained_events": retained_events, "event_count": event_count,
            "rejection_counts": dict(sorted(rejection_counts.items())),
        },
    )


def main() -> int:
    search_url = os.environ.get("YAHOO_REALTIME_URL", DEFAULT_SEARCH_URL).strip()
    min_retweets = int(os.environ.get("YAHOO_MIN_RETWEETS", "3"))
    validate_search_url(search_url)
    now = datetime.now(UTC).replace(microsecond=0)
    existing = read_json_array(OUTPUT_PATH)
    known_x_ids = x_status_ids(read_json_array(X_EVENTS_PATH))
    try:
        html_text, http_status, final_url = fetch_page(search_url)
    except (RuntimeError, ValueError) as exc:
        write_health(
            status="degraded", reason=f"Yahoo realtime fetch failed; retained existing cache: {exc}",
            search_url=search_url, http_status=None, final_url=None, html_bytes=0,
            fetched_candidates=0, accepted_candidates=0, rejected_candidates=0,
            retained_events=len(existing), event_count=len(existing), rejection_counts=Counter(),
        )
        print(f"Yahoo realtime discovery failed; retained {len(existing)} cached events: {exc}")
        return 0
    candidates = extract_candidates(html_text)
    if not candidates:
        write_health(
            status="degraded", reason="Yahoo realtime page contained no parseable post candidates; retained existing cache",
            search_url=search_url, http_status=http_status, final_url=final_url,
            html_bytes=len(html_text.encode("utf-8")), fetched_candidates=0, accepted_candidates=0,
            rejected_candidates=0, retained_events=len(existing), event_count=len(existing),
            rejection_counts=Counter({"no_parseable_candidates": 1}),
        )
        print(f"Yahoo realtime parser found no candidates; retained {len(existing)} cached events")
        return 0
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    rejection_counts: Counter[str] = Counter()
    for candidate in candidates:
        event, rejection = candidate_to_event(
            candidate, now=now, min_retweets=min_retweets, known_x_ids=known_x_ids
        )
        if event is not None:
            accepted.append(event)
            continue
        reason = rejection or "unknown"
        rejection_counts[reason] += 1
        rejected.append(
            {
                "status_id": candidate.get("status_id"), "url": candidate.get("url"), "reason": reason,
                "retweet_count": candidate.get("retweet_count"),
                "text_excerpt": re.sub(r"\s+", " ", str(candidate.get("text") or "")).strip()[:360],
            }
        )
    merged = merge_cache(existing, accepted, now)
    accepted_ids = {str(item["source_id"]) for item in accepted}
    retained = sum(1 for item in merged if str(item.get("source_id")) not in accepted_ids)
    atomic_write_json(OUTPUT_PATH, merged)
    atomic_write_json(REJECTED_PATH, rejected[:200])
    write_health(
        status="ok", reason=None, search_url=search_url, http_status=http_status, final_url=final_url,
        html_bytes=len(html_text.encode("utf-8")), fetched_candidates=len(candidates),
        accepted_candidates=len(accepted), rejected_candidates=len(rejected), retained_events=retained,
        event_count=len(merged), rejection_counts=rejection_counts,
    )
    print(
        f"Yahoo realtime discovery accepted {len(accepted)} of {len(candidates)} candidates; "
        f"cache has {len(merged)} events"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
