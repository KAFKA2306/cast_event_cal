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
PARSER_VERSION = "1.2"
FOREIGN_TIMEZONE_RE = re.compile(r"\\b(?:BST|UTC|GMT|PST|PDT|EST|EDT|CET|CEST)\\b", re.IGNORECASE)
STATUS_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:x|twitter)\.com/[^\s\"'<>\\]+/status/(\d+)", re.IGNORECASE
)
STATUS_ID_RE = re.compile(r"\d{10,25}")
VRCHAT_RE = re.compile(r"(?i)(?:#?vrchat|#?vrc\b)")
YAHOO_START_MARKER_RE = re.compile(r"^\s*START(?=\s)")
YAHOO_END_MARKER_RE = re.compile(r"(?<=\s)END\s*$")
FULLWIDTH_DIGIT_TRANSLATION = str.maketrans("０１２３４５６７８９", "0123456789")
CLOCK_PUNCTUATION_TRANSLATION = str.maketrans({
    "：": ":", "˸": ":", "꞉": ":", "∶": ":", "︓": ":", "﹕": ":",
    "／": "/", "⁄": "/", "．": ".", "－": "-",
})
ENGLISH_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
ENGLISH_DATE_RE = re.compile(
    r"(?i)\b(?P<day>3[01]|[12]?\d)(?:st|nd|rd|th)?\s+"
    r"(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)\.?[,]?\s+(?P<year>20\d{2})\b"
)
TEXT_KEYS = ("displayText", "full_text", "fullText", "tweetText", "text")
URL_KEYS = ("url", "tweetUrl", "statusUrl", "permalink")
ID_KEYS = ("id", "tweetId", "statusId", "id_str", "rest_id")
AUTHOR_KEYS = ("screenName", "screen_name", "username", "userName", "handle")
RETWEET_KEYS = ("rtCount", "retweet_count", "retweetCount", "repost_count", "repostCount")
CONVERSATION_ID_KEYS = ("conversation_id_str", "conversation_id", "conversationId")
IN_REPLY_TO_STATUS_ID_KEYS = ("in_reply_to_status_id_str", "in_reply_to_status_id", "inReplyToStatusId")
QUOTED_STATUS_ID_KEYS = ("quoted_status_id_str", "quoted_status_id", "quotedStatusId")
EXPANDED_URL_KEYS = ("expanded_url", "expandedUrl", "unwound_url", "unwoundUrl")
EVENT_TERMS = {
    "イベント", "参加方法", "参加条件", "開催", "join", "ジョイン", "リクイン", "reqin",
    "リクエストインバイト", "request invite", "営業", "公演", "集会", "ライブ", "ツアー",
    "開場", "group instance", "グループインスタンス", "join先",
}
RECRUITMENT_TERMS = {"募集", "応募", "締切", "〆切", "テスター"}
PRODUCT_TERMS = {
    "booth", "販売", "発売", "配布", "価格", "セール", "商品", "patreon", "記事",
    "キーチェーン", "衣装", "アバター",
}
GIVEAWAY_TERMS = {
    "プレゼント", "giveaway", "rpキャンペーン", "抽選", "当選", "フォロー＆rp", "フォロー&rp",
}


class JsonScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.capturing = False
        self.parts: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        values = {key.lower(): value or "" for key, value in attrs}
        if "json" in values.get("type", "").lower() or values.get("id", "").lower() in {
            "__next_data__",
            "__initial_state__",
        }:
            self.capturing = True
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.capturing:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self.capturing:
            self.scripts.append("".join(self.parts).strip())
            self.capturing = False
            self.parts = []


def utc_text(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def direct_string(mapping: dict[str, Any], keys: Iterable[str]) -> str | None:
    folded = {str(key).casefold(): value for key, value in mapping.items()}
    for key in keys:
        value = folded.get(key.casefold())
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def direct_integer(mapping: dict[str, Any], keys: Iterable[str]) -> int | None:
    folded = {str(key).casefold(): value for key, value in mapping.items()}
    for key in keys:
        value = folded.get(key.casefold())
        if isinstance(value, bool) or value is None:
            continue
        try:
            return int(str(value).replace(",", ""))
        except ValueError:
            continue
    return None


def direct_status_identifier(mapping: dict[str, Any], keys: Iterable[str]) -> str | None:
    folded = {str(key).casefold(): value for key, value in mapping.items()}
    for key in keys:
        value = folded.get(key.casefold())
        text = str(value).strip() if isinstance(value, (int, str)) else ""
        if STATUS_ID_RE.fullmatch(text):
            return text
    return None


def expanded_urls(mapping: dict[str, Any]) -> list[str]:
    """Extract canonical link evidence attached to the same Yahoo/X post."""
    results: set[str] = set()
    for container_key in ("entities", "extended_entities"):
        container = mapping.get(container_key)
        if not isinstance(container, (dict, list)):
            continue
        for node in walk(container):
            if not isinstance(node, dict):
                continue
            folded = {str(key).casefold(): value for key, value in node.items()}
            for key in EXPANDED_URL_KEYS:
                value = folded.get(key.casefold())
                if isinstance(value, str) and value.startswith(("https://", "http://")):
                    results.add(value.strip())
    return sorted(results)[:20]


def status_id(mapping: dict[str, Any]) -> str | None:
    for key in URL_KEYS:
        value = mapping.get(key)
        if isinstance(value, str) and (match := STATUS_RE.search(value.replace("\\/", "/"))):
            return match.group(1)
    for key in ID_KEYS:
        value = mapping.get(key)
        text = str(value).strip() if isinstance(value, (int, str)) else ""
        if STATUS_ID_RE.fullmatch(text):
            return text
    return None


def status_url(mapping: dict[str, Any], post_id: str) -> str:
    for key in URL_KEYS:
        value = mapping.get(key)
        if not isinstance(value, str):
            continue
        normalized = value.replace("\\/", "/")
        if STATUS_RE.search(normalized):
            return normalized if normalized.startswith("http") else f"https://{normalized.lstrip('/')}"
    return f"https://x.com/i/web/status/{post_id}"


def clean_yahoo_text(text: str) -> str:
    cleaned = unescape(text).replace("\tSTART\t", " ").replace("\tEND\t", " ")
    cleaned = YAHOO_START_MARKER_RE.sub("", cleaned, count=1)
    cleaned = YAHOO_END_MARKER_RE.sub("", cleaned, count=1)
    return cleaned.strip()


def candidate_from_mapping(mapping: dict[str, Any]) -> dict[str, Any] | None:
    text = direct_string(mapping, TEXT_KEYS)
    post_id = status_id(mapping)
    if not text or not post_id:
        return None
    text = clean_yahoo_text(text)
    candidate = {
        "status_id": post_id,
        "url": status_url(mapping, post_id),
        "text": text,
        "author": direct_string(mapping, AUTHOR_KEYS),
        "retweet_count": direct_integer(mapping, RETWEET_KEYS),
    }
    optional_ids = {
        "conversation_id": direct_status_identifier(mapping, CONVERSATION_ID_KEYS),
        "in_reply_to_status_id": direct_status_identifier(mapping, IN_REPLY_TO_STATUS_ID_KEYS),
        "quoted_status_id": direct_status_identifier(mapping, QUOTED_STATUS_ID_KEYS),
    }
    candidate.update({key: value for key, value in optional_ids.items() if value})
    links = expanded_urls(mapping)
    if links:
        candidate["linked_urls"] = links
    return candidate


def extract_candidates(html_text: str) -> list[dict[str, Any]]:
    collector = JsonScriptCollector()
    collector.feed(html_text)
    selected: dict[str, dict[str, Any]] = {}
    for raw in collector.scripts:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in walk(payload):
            if not isinstance(node, dict) or (candidate := candidate_from_mapping(node)) is None:
                continue
            post_id = str(candidate["status_id"])
            current = selected.get(post_id)
            candidate_score = (
                candidate.get("retweet_count") is not None,
                len(str(candidate["text"])),
                sum(
                    bool(candidate.get(key))
                    for key in ("conversation_id", "in_reply_to_status_id", "quoted_status_id")
                ) + len(candidate.get("linked_urls") or []),
            )
            current_score = (
                (
                    current.get("retweet_count") is not None,
                    len(str(current.get("text", ""))),
                    sum(
                        bool(current.get(key))
                        for key in ("conversation_id", "in_reply_to_status_id", "quoted_status_id")
                    ) + len(current.get("linked_urls") or []),
                )
                if current else (False, -1, -1)
            )
            if current is None or candidate_score > current_score:
                selected[post_id] = candidate
    return list(selected.values())


def normalize_text(text: str) -> str:
    normalized = (
        text.translate(FULLWIDTH_DIGIT_TRANSLATION)
        .translate(CLOCK_PUNCTUATION_TRANSLATION)
        .replace("〜", "~").replace("～", "~")
    )

    def english_date(match: re.Match[str]) -> str:
        month = ENGLISH_MONTHS[match.group("month").casefold().rstrip(".")]
        return f"{match.group('year')}/{month:02d}/{int(match.group('day')):02d}"

    return ENGLISH_DATE_RE.sub(english_date, normalized)


def _datetime_from_match(match: re.Match[str], anchor: datetime) -> datetime | None:
    values = match.groupdict()
    hour = int(values["hour"])
    period = (values.get("period_before") or values.get("period_after") or "").casefold()
    if period and hour <= 12:
        if period == "am" and hour == 12:
            hour = 0
        elif period == "pm" and hour < 12:
            hour += 12
    try:
        event_at = datetime(
            int(values.get("year") or anchor.year),
            int(values["month"]),
            int(values["day"]),
            hour,
            int(values.get("minute") or 0),
            tzinfo=JST,
        )
    except ValueError:
        return None
    if not values.get("year") and event_at < anchor - timedelta(days=2):
        try:
            event_at = event_at.replace(year=event_at.year + 1)
        except ValueError:
            return None
    return event_at


def parse_event_datetime(text: str, anchor: datetime) -> datetime | None:
    normalized = normalize_text(text)
    clock = (
        r"(?:(?P<period_before>AM|PM)\s*)?"
        r"(?P<hour>[01]?\d|2[0-3])(?:[:時](?P<minute>\d{2})?)"
        r"(?:\s*(?P<period_after>AM|PM))?"
    )
    date_patterns = [
        r"(?P<year>20\d{2})[./年-](?P<month>\d{1,2})[./月-](?P<day>\d{1,2})日?",
        r"(?P<month>\d{1,2})[./月-](?P<day>\d{1,2})日?",
    ]

    # When a post presents multiple timezone renderings of the same event,
    # prefer the explicitly labelled JST rendering instead of interpreting a
    # preceding foreign clock as JST.
    for date_pattern in date_patterns:
        for pattern in (
            rf"{date_pattern}\s*(?:[（(]?[月火水木金土日][）)]?)?\s*(?:\(?JST\)?)\s*{clock}",
            rf"{date_pattern}\s*(?:[（(]?[月火水木金土日][）)]?)?.{{0,20}}?{clock}\s*(?:\(?JST\)?)",
        ):
            match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return _datetime_from_match(match, anchor)

    # A foreign-zone clock without a nearby explicit JST representation is not
    # safe to reinterpret. Fail closed rather than silently shifting the event.
    if FOREIGN_TIMEZONE_RE.search(normalized):
        return None

    patterns = [
        rf"{date_patterns[0]}(?:\s*[（(]?[月火水木金土日][）)]?)?.{{0,40}}?{clock}",
        rf"{date_patterns[1]}(?:\s*[（(]?[月火水木金土日][）)]?)?.{{0,40}}?{clock}",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _datetime_from_match(match, anchor)

    relative = re.search(
        rf"(?P<day>本日|今日|明日).{{0,30}}?{clock}",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not relative:
        return None
    day = (anchor + timedelta(days=1 if relative.group("day") == "明日" else 0)).date()
    hour = int(relative.group("hour"))
    period = (relative.group("period_before") or relative.group("period_after") or "").casefold()
    if period and hour <= 12:
        if period == "am" and hour == 12:
            hour = 0
        elif period == "pm" and hour < 12:
            hour += 12
    return datetime(
        day.year,
        day.month,
        day.day,
        hour,
        int(relative.group("minute") or 0),
        tzinfo=JST,
    )


def classify(text: str) -> tuple[str | None, str | None]:
    folded = text.casefold()
    if not VRCHAT_RE.search(text):
        return None, "not_vrchat"
    has_event = any(term in folded for term in EVENT_TERMS)
    has_recruitment = any(term in folded for term in RECRUITMENT_TERMS)
    has_product = any(term in folded for term in PRODUCT_TERMS)
    has_giveaway = any(term in folded for term in GIVEAWAY_TERMS)
    if has_giveaway and not has_event:
        return None, "giveaway_only"
    if has_product and not has_event and not (has_recruitment and "テスター" in folded):
        return None, "product_only"
    if has_recruitment and any(term in folded for term in ("締切", "〆切", "応募", "テスター")):
        return "recruitment_deadline", None
    return ("event", None) if has_event else (None, "missing_event_marker")


def title_from_text(text: str, category: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line and not line.startswith("http")]
    if category == "recruitment_deadline":
        selected = next((line for line in lines if any(term in line for term in RECRUITMENT_TERMS)), None)
    else:
        selected = next(
            (line for line in lines if VRCHAT_RE.search(line) or any(term in line.casefold() for term in EVENT_TERMS)),
            None,
        )
    selected = selected or (lines[0] if lines else "VRChatイベント")
    return selected[:96] + ("…" if len(selected) > 96 else "")


def known_x_ids(events: Iterable[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for event in events:
        source_id = str(event.get("source_id") or "")
        if source_id.startswith("x:"):
            result.add(source_id.split(":", 1)[1])
        if match := STATUS_RE.search(str(event.get("url") or "")):
            result.add(match.group(1))
    return result


def candidate_to_event_at(
    candidate: dict[str, Any],
    *,
    event_at: datetime | None,
    now: datetime,
    min_retweets: int,
    x_ids: set[str],
) -> tuple[dict[str, Any] | None, str | None]:
    """Build an event from a resolver-supplied timestamp after normal policy checks."""
    post_id = str(candidate.get("status_id") or "")
    text = clean_yahoo_text(str(candidate.get("text") or ""))
    if not STATUS_ID_RE.fullmatch(post_id):
        return None, "invalid_status_id"
    if post_id in x_ids:
        return None, "duplicate_x_source"
    if len(text) < 12:
        return None, "missing_text"
    if len(text) > 1200 or any(marker in text for marker in ('\\",\\"', '"displayText"', '"rtCount"')):
        return None, "malformed_text"
    category, reason = classify(text)
    if reason:
        return None, reason
    retweets = candidate.get("retweet_count")
    if retweets is None:
        return None, "retweet_count_missing"
    try:
        retweets = int(retweets)
    except (TypeError, ValueError):
        return None, "retweet_count_invalid"
    if retweets < min_retweets:
        return None, "retweet_below_threshold"
    if event_at is None:
        return None, "missing_datetime"
    event_at = event_at.astimezone(JST)
    if event_at < now.astimezone(JST) - timedelta(hours=12):
        return None, "past_event"
    if event_at > now.astimezone(JST) + timedelta(days=180):
        return None, "too_far_future"
    author = str(candidate.get("author") or "").strip().lstrip("@")
    event = {
        "source_id": f"yahoo:x:{post_id}",
        "title": title_from_text(text, str(category)),
        "starts_at": utc_text(event_at),
        "organizer": f"@{author}" if author else None,
        "location": "オンライン" if category == "recruitment_deadline" else "VRChat",
        "description": re.sub(r"\s+", " ", text).strip(),
        "url": candidate.get("url") or f"https://x.com/i/web/status/{post_id}",
        "category": category,
        "tags": ["VRChat", "Yahoo!リアルタイム検索", "機械判定", "リポスト3件以上"],
        "confidence": 0.9,
        "review_required": False,
    }
    return {key: value for key, value in event.items() if value is not None}, None


def candidate_to_event(
    candidate: dict[str, Any], *, now: datetime, min_retweets: int, x_ids: set[str]
) -> tuple[dict[str, Any] | None, str | None]:
    text = clean_yahoo_text(str(candidate.get("text") or ""))
    event_at = parse_event_datetime(text, now.astimezone(JST))
    return candidate_to_event_at(
        candidate,
        event_at=event_at,
        now=now,
        min_retweets=min_retweets,
        x_ids=x_ids,
    )

def parse_instant(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    return parsed.astimezone(UTC)


def clean_cached_event_text(event: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(event)
    title = clean_yahoo_text(str(cleaned.get("title") or ""))
    description = clean_yahoo_text(str(cleaned.get("description") or ""))
    if title:
        cleaned["title"] = title
    if description:
        cleaned["description"] = re.sub(r"\s+", " ", description).strip()
    return cleaned


def cached_event_is_valid(event: dict[str, Any], now: datetime) -> bool:
    start = parse_instant(str(event.get("starts_at") or ""))
    source_id = str(event.get("source_id") or "")
    text = str(event.get("description") or "").strip()
    if not start or not source_id.startswith("yahoo:x:"):
        return False
    if not now - timedelta(days=1) <= start <= now + timedelta(days=180):
        return False
    if len(text) < 12 or len(text) > 1200:
        return False
    if any(marker in text for marker in ('\\",\\"', '"displayText"', '"rtCount"')):
        return False
    return classify(text)[1] is None


def merge_cache(existing: list[dict[str, Any]], fresh: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for raw_event in existing:
        event = clean_cached_event_text(raw_event)
        if cached_event_is_valid(event, now):
            selected[str(event["source_id"])] = event
    for raw_event in fresh:
        event = clean_cached_event_text(raw_event)
        if cached_event_is_valid(event, now):
            selected[str(event["source_id"])] = event
    return sorted(selected.values(), key=lambda item: (str(item.get("starts_at")), str(item.get("title"))))


def validate_search_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "search.yahoo.co.jp" or parsed.path != "/realtime/search":
        raise ValueError("Yahoo realtime URL must use https://search.yahoo.co.jp/realtime/search")


def fetch_page(url: str) -> tuple[str, int, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
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
                if "html" not in response.headers.get("content-type", "").casefold():
                    raise RuntimeError("unexpected content type")
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
    final_url: str | None, html_bytes: int, fetched: int, accepted: int, rejected: int,
    retained: int, event_count: int, rejection_counts: Counter[str],
) -> None:
    write_json(
        HEALTH_PATH,
        {
            "schema_version": "1.0", "parser_version": PARSER_VERSION,
            "generated_at": utc_text(datetime.now(UTC)), "status": status, "reason": reason,
            "search_url": search_url, "http_status": http_status, "final_url": final_url,
            "html_bytes": html_bytes, "fetched_candidates": fetched, "accepted_candidates": accepted,
            "rejected_candidates": rejected, "retained_events": retained, "event_count": event_count,
            "rejection_counts": dict(sorted(rejection_counts.items())),
        },
    )


def main() -> int:
    search_url = os.environ.get("YAHOO_REALTIME_URL", DEFAULT_SEARCH_URL).strip()
    min_retweets = int(os.environ.get("YAHOO_MIN_RETWEETS", "3"))
    validate_search_url(search_url)
    now = datetime.now(UTC).replace(microsecond=0)
    existing = read_array(OUTPUT_PATH)
    x_ids = known_x_ids(read_array(X_EVENTS_PATH))
    try:
        html_text, http_status, final_url = fetch_page(search_url)
    except RuntimeError as exc:
        write_health(
            status="degraded", reason=f"fetch failed; retained cache: {exc}", search_url=search_url,
            http_status=None, final_url=None, html_bytes=0, fetched=0, accepted=0, rejected=0,
            retained=len(existing), event_count=len(existing), rejection_counts=Counter(),
        )
        return 0
    candidates = extract_candidates(html_text)
    if not candidates:
        write_health(
            status="degraded", reason="no direct Yahoo post objects; retained cache", search_url=search_url,
            http_status=http_status, final_url=final_url, html_bytes=len(html_text.encode()), fetched=0,
            accepted=0, rejected=0, retained=len(existing), event_count=len(existing),
            rejection_counts=Counter({"no_direct_post_objects": 1}),
        )
        return 0
    accepted_events: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    for candidate in candidates:
        event, reason = candidate_to_event(candidate, now=now, min_retweets=min_retweets, x_ids=x_ids)
        if event:
            accepted_events.append(event)
            continue
        rejection = reason or "unknown"
        reasons[rejection] += 1
        rejected_rows.append(
            {
                "status_id": candidate.get("status_id"), "url": candidate.get("url"),
                "reason": rejection, "retweet_count": candidate.get("retweet_count"),
                "text_excerpt": re.sub(r"\s+", " ", str(candidate.get("text") or "")).strip()[:360],
            }
        )
    merged = merge_cache(existing, accepted_events, now)
    accepted_ids = {str(item["source_id"]) for item in accepted_events}
    retained = sum(1 for item in merged if str(item.get("source_id")) not in accepted_ids)
    write_json(OUTPUT_PATH, merged)
    write_json(REJECTED_PATH, rejected_rows[:200])
    write_health(
        status="ok", reason=None, search_url=search_url, http_status=http_status, final_url=final_url,
        html_bytes=len(html_text.encode()), fetched=len(candidates), accepted=len(accepted_events),
        rejected=len(rejected_rows), retained=retained, event_count=len(merged), rejection_counts=reasons,
    )
    print(f"Yahoo realtime: accepted={len(accepted_events)} rejected={len(rejected_rows)} cached={len(merged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
