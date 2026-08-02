from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

JST = ZoneInfo("Asia/Tokyo")
OUTPUT_PATH = Path("data/x_events.json")
HEALTH_PATH = Path("data/x_discovery_health.json")
API_URL = "https://api.x.com/2/tweets/search/recent"
DEFAULT_QUERY = (
    'lang:ja (イベント OR 参加方法 OR 参加条件 OR 開催 OR 主催 OR join OR ジョイン '
    'OR リクイン OR reqin OR リクエストインバイト OR "request invite" OR 本日 OR 営業 OR 応募) '
    '(VRChat OR VRC) -is:retweet -is:reply'
)

EVENT_TERMS = {
    "イベント", "開催", "参加方法", "参加条件", "営業", "公演", "集会", "ライブ",
    "ツアー", "当日join", "ジョイン", "リクイン", "reqin", "request invite",
}
RECRUITMENT_TERMS = {"募集", "応募", "締切", "テスター"}
PRODUCT_TERMS = {
    "booth", "販売開始", "発売", "プレゼント企画", "giveaway", "rpキャンペーン",
    "プレゼントキャンペーン",
}
WEEKDAY_RE = r"(?:\([月火水木金土日]\)|（[月火水木金土日]）)?"


def utc_text(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_existing() -> list[dict[str, Any]]:
    if not OUTPUT_PATH.exists():
        return []
    try:
        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def write_health(
    *, status: str, reason: str | None, query: str, event_count: int,
    fetched_posts: int, accepted_posts: int, errors: list[str] | None = None,
) -> None:
    HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "generated_at": utc_text(datetime.now(UTC)),
        "status": status,
        "reason": reason,
        "query": query,
        "event_count": event_count,
        "fetched_posts": fetched_posts,
        "accepted_posts": accepted_posts,
        "errors": errors or [],
    }
    HEALTH_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_post_datetime(text: str, created_at: datetime) -> datetime | None:
    normalized = text.replace("：", ":")
    patterns = [
        rf"(?P<year>20\d{{2}})[./年-](?P<month>\d{{1,2}})[./月-](?P<day>\d{{1,2}})日?{WEEKDAY_RE}.*?(?P<hour>[01]?\d|2[0-3])[:時](?P<minute>\d{{2}})?",
        rf"(?P<month>\d{{1,2}})[./月-](?P<day>\d{{1,2}})日?{WEEKDAY_RE}.*?(?P<hour>[01]?\d|2[0-3])[:時](?P<minute>\d{{2}})?",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        groups = match.groupdict()
        year = int(groups.get("year") or created_at.year)
        month = int(groups["month"])
        day = int(groups["day"])
        hour = int(groups["hour"])
        minute = int(groups.get("minute") or 0)
        try:
            candidate = datetime(year, month, day, hour, minute, tzinfo=JST)
        except ValueError:
            return None
        if not groups.get("year") and candidate < created_at - timedelta(days=45):
            try:
                candidate = candidate.replace(year=candidate.year + 1)
            except ValueError:
                return None
        return candidate
    return None


def classify(text: str) -> str | None:
    lowered = text.casefold()
    has_event = any(term in lowered for term in EVENT_TERMS)
    has_recruitment = any(term in lowered for term in RECRUITMENT_TERMS)
    has_product = any(term in lowered for term in PRODUCT_TERMS)
    if has_recruitment and ("締切" in text or "応募" in text):
        return "recruitment_deadline"
    if has_event:
        return "event"
    if has_product:
        return None
    return None


def title_from_text(text: str, category: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]
    if category == "recruitment_deadline":
        candidate = next(
            (line for line in lines if "募集" in line or "応募" in line),
            lines[0] if lines else "VRChat関連募集",
        )
    else:
        quoted = next(
            (
                line.strip("『』「」【】")
                for line in lines
                if line.startswith(("『", "「", "【")) and line.endswith(("』", "」", "】"))
            ),
            None,
        )
        candidate = quoted or next(
            (
                line for line in lines
                if not re.search(r"\d{1,2}[/:月日]\d{1,2}", line)
                and not line.startswith(("🗓", "📅", "⏰"))
            ),
            lines[0] if lines else "VRChatイベント",
        )
    return candidate[:96] + ("…" if len(candidate) > 96 else "")


def post_to_event(
    post: dict[str, Any], usernames: dict[str, str], *, min_retweets: int,
) -> dict[str, Any] | None:
    text = str(post.get("text") or "").strip()
    created_text = str(post.get("created_at") or "")
    if not text or not created_text:
        return None
    created_at = datetime.fromisoformat(created_text.replace("Z", "+00:00")).astimezone(JST)
    event_at = parse_post_datetime(text, created_at)
    category = classify(text)
    if event_at is None or category is None:
        return None

    metrics = post.get("public_metrics") or {}
    retweets = int(metrics.get("retweet_count") or 0)
    strong_marker = any(marker in text.casefold() for marker in ("参加方法", "当日join", "開催", "営業", "締切"))
    if retweets < min_retweets and not strong_marker:
        return None

    post_id = str(post.get("id") or "")
    username = usernames.get(str(post.get("author_id") or ""), "")
    url = f"https://x.com/{username}/status/{post_id}" if username else f"https://x.com/i/web/status/{post_id}"
    tags = ["VRChat", "X", "自動取得"]
    if category == "recruitment_deadline":
        tags.extend(["募集", "締切"])
    else:
        tags.append("イベント")
    return {
        "source_id": f"x:{post_id}",
        "title": title_from_text(text, category),
        "starts_at": utc_text(event_at),
        "organizer": f"@{username}" if username else None,
        "location": "VRChat" if category == "event" else "オンライン",
        "description": re.sub(r"\s+", " ", text).strip(),
        "url": url,
        "category": category,
        "tags": tags,
        "confidence": 0.82,
        "review_required": False,
    }


def main() -> int:
    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    query = os.environ.get("X_EVENT_QUERY", DEFAULT_QUERY).strip()
    min_retweets = int(os.environ.get("X_EVENT_MIN_RETWEETS", "3"))
    existing = read_existing()
    if not token:
        write_health(
            status="skipped",
            reason="X_BEARER_TOKEN is not configured; retained existing cache",
            query=query,
            event_count=len(existing),
            fetched_posts=0,
            accepted_posts=0,
        )
        print(f"X discovery skipped; retained {len(existing)} cached events")
        return 0

    params = {
        "query": query,
        "max_results": 100,
        "tweet.fields": "created_at,author_id,public_metrics",
        "expansions": "author_id",
        "user.fields": "username,name",
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(API_URL, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        write_health(
            status="degraded",
            reason="X API request failed; retained existing cache",
            query=query,
            event_count=len(existing),
            fetched_posts=0,
            accepted_posts=0,
            errors=[str(exc)],
        )
        print(f"X discovery failed; retained {len(existing)} cached events: {exc}")
        return 0

    usernames = {
        str(item.get("id")): str(item.get("username"))
        for item in payload.get("includes", {}).get("users", [])
        if item.get("id") and item.get("username")
    }
    posts = [item for item in payload.get("data", []) if isinstance(item, dict)]
    accepted = [
        event for item in posts
        if (event := post_to_event(item, usernames, min_retweets=min_retweets)) is not None
    ]
    unique = {str(item["source_id"]): item for item in accepted}
    events = sorted(unique.values(), key=lambda item: (str(item["starts_at"]), str(item["title"])))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_health(
        status="ok",
        reason=None,
        query=query,
        event_count=len(events),
        fetched_posts=len(posts),
        accepted_posts=len(events),
    )
    print(f"X discovery accepted {len(events)} of {len(posts)} posts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
