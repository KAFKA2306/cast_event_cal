from __future__ import annotations

import re
import unicodedata
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from scripts import fetch_yahoo_realtime as implementation

JST = ZoneInfo("Asia/Tokyo")
PARSER_VERSION = "1.9"
DEFAULT_EVENT_HOUR = 22
MAX_FUTURE_DAYS = 180

EVENT_HASHTAG_RE = re.compile(
    r"(?i)(?:#(?:vrc|vrchat)[_\-]?(?:イベント|event)|#\S*(?:集会|営業|祭|フェス|ライブ|公演|上映|説明会|体験会)\S*)"
)
GENERIC_EVENT_RE = re.compile(
    r"(?i)(?:イベント|event|催し|企画|営業|公演|集会|交流会|説明会|体験会|撮影会|ライブ|"
    r"DJ|祭り|フェス|上映会|朗読会|舞台|大会|開会式|フォトコン|ツアー|案内会)"
)
EVENT_ACTION_RE = re.compile(
    r"(?i)(?:開催|open|オープン|開場|開始|営業|実施|開演|出展|上映|上演|募集開始|受付開始)"
)
ATTENDANCE_RE = re.compile(
    r"(?i)(?:参加|来場|ご来場|ご来店|遊びに来|遊びにき|お越し|お待ち|入場|観覧|見学)"
)
ACCESS_RE = re.compile(
    r"(?i)(?:\bjoin\b|ジョイン|リクイン|reqin|request\s*invite|リクエストインバイト|"
    r"group\s*\+?|group\s*instance|グループ[＋+]?インスタンス|グループインスタンス|"
    r"グループパブリック|フレンドインスタンス|インスタンス(?:へ|に|先|オープン)|"
    r"招待をリクエスト|invite\s*only|参加リクエスト|フレンド申請)"
)
SCHEDULE_RE = re.compile(
    r"(?i)(?:日時|日程|スケジュール|予定|毎週|今週|来週|本日|今日|今夜|明日|明後日|"
    r"20\d{2}[./年-]\d{1,2}[./月-]\d{1,2}|\d{1,2}[./月-]\d{1,2}|"
    r"[月火水木金土日]曜|(?:[01]?\d|2[0-9])(?:[:時]\d{0,2}|時半))"
)
RECRUITMENT_RE = re.compile(
    r"(?i)(?:募集|応募|締切|エントリー|スタッフ|出演者|キャスト|協賛|参加者募集|受付)"
)
BROADCAST_RE = re.compile(
    r"(?i)(?:配信予定|コラボ配信|ライブ配信|youtube配信|配信枠|生配信|プレミア公開)"
)
WORLD_DESCRIPTION_RE = re.compile(
    r"(?i)(?:ワールド紹介|ワールドを更新|常設ワールド|いつでも|公開しました)"
)
NON_EVENT_NOTICE_RE = re.compile(
    r"(?i)(?:障害情報|障害発生|メンテナンス|不具合|API(?:の|に)?(?:エラー|遅延)|"
    r"ログイン障害|アップデート情報)"
)
OFFLINE_ONLY_RE = re.compile(
    r"(?i)(?:VRCとは関係ない|VRChatとは関係ない|VRCのオフ会|VRChatのオフ会|"
    r"リアルイベント|オフラインイベント|リアル会場のみ|現地開催のみ)"
)
CANCEL_RE = re.compile(
    r"(?i)(?:開催を?延期|延期します|延期とな|開催中止|中止します|中止とな|開催見送り|"
    r"本日は?お休み|営業を?休止|休業します|イベントは?お休み)"
)
RESCHEDULED_RE = re.compile(
    r"(?i)(?:延期となっていた.{0,40}(?:今夜|本日|今日|明日)?.{0,20}開催|再開催|振替開催|"
    r"改めて開催|延期先|新日程)"
)
RECAP_RE = re.compile(
    r"(?i)(?:ご参加ありがとうございました|ご来場ありがとうございました|お越しいただきありがとうございました|"
    r"お疲れさまでした|お疲れ様でした|終了しました|無事終了|開催しました|開催されました|"
    r"参加してきました|参加しました|お邪魔しました|行ってきました|振り返り|アフターレポート|"
    r"イベントレポート|当日の様子|集合写真|写真を撮りました|楽しかったです|盛り上がりました|"
    r"本日行われた|昨日の.{0,30}(?:集会|イベント|営業|ライブ)|集会が終了|閉場|終わったあと|"
    r"楽しい思い出|担当していました|出展しました)"
)
PERSONAL_PLAN_RE = re.compile(
    r"(?i)(?:参加予定です|参加する予定|お邪魔する予定|見に行く予定|遊びに行く予定|"
    r"オフ会のため|日帰りで|現地へ行き|リアル接待)"
)


def normalize_text(text: str) -> str:
    return (
        unicodedata.normalize("NFKC", text)
        .replace("：", ":")
        .replace("／", "/")
        .replace("．", ".")
        .replace("－", "-")
        .replace("〜", "~")
        .replace("～", "~")
    )


def _safe_datetime(year: int, month: int, day: int, hour: int, minute: int) -> datetime | None:
    day_offset, normalized_hour = divmod(hour, 24)
    try:
        return datetime(year, month, day, normalized_hour, minute, tzinfo=JST) + timedelta(days=day_offset)
    except ValueError:
        return None


def _roll_year_if_needed(value: datetime, anchor: datetime, explicit_year: bool) -> datetime | None:
    if explicit_year or value >= anchor - timedelta(days=180):
        return value
    try:
        next_year = value.replace(year=value.year + 1)
    except ValueError:
        return value
    return next_year if next_year <= anchor + timedelta(days=180) else value


def _clock_groups(match: re.Match[str]) -> tuple[int, int]:
    hour = int(match.group("hour"))
    minute_text = match.groupdict().get("minute")
    half = bool(match.groupdict().get("half"))
    return hour, 30 if half else int(minute_text or 0)


def _weekday_date(anchor: datetime, weekday: str, prefix: str) -> datetime.date:
    target = {name: index for index, name in enumerate("月火水木金土日")}[weekday]
    days_ahead = (target - anchor.weekday()) % 7
    if prefix.startswith("来週"):
        days_ahead += 7
    elif prefix.startswith("次") and days_ahead == 0:
        days_ahead = 7
    elif prefix.startswith("毎週") and days_ahead == 0:
        days_ahead = 7
    return (anchor + timedelta(days=days_ahead)).date()


def _is_cancelled(text: str) -> bool:
    return bool(CANCEL_RE.search(text)) and not bool(RESCHEDULED_RE.search(text))


def strong_occurrence(text: str) -> bool:
    normalized = normalize_text(text)
    has_schedule = bool(SCHEDULE_RE.search(normalized))
    has_event_hashtag = bool(EVENT_HASHTAG_RE.search(normalized))
    has_generic_event = bool(GENERIC_EVENT_RE.search(normalized))
    has_action = bool(EVENT_ACTION_RE.search(normalized))
    has_attendance = bool(ATTENDANCE_RE.search(normalized))
    has_access = bool(ACCESS_RE.search(normalized))
    has_recruitment = bool(RECRUITMENT_RE.search(normalized))
    return has_schedule and (
        has_event_hashtag
        or (has_access and (has_generic_event or has_action or has_attendance))
        or (has_generic_event and has_action)
        or (has_action and has_attendance)
        or (has_generic_event and has_recruitment)
    )


def allow_inferred_datetime(text: str) -> bool:
    normalized = normalize_text(text)
    if not implementation.VRCHAT_RE.search(normalized):
        return False
    if RECAP_RE.search(normalized) or PERSONAL_PLAN_RE.search(normalized):
        return False
    if _is_cancelled(normalized) or OFFLINE_ONLY_RE.search(normalized):
        return False
    if NON_EVENT_NOTICE_RE.search(normalized):
        return False
    return strong_occurrence(normalized)


def parse_event_datetime(text: str, anchor: datetime) -> datetime | None:
    normalized = normalize_text(text)
    anchor = anchor.astimezone(JST)
    clock = r"(?P<hour>[01]?\d|2[0-9])(?:(?::|時)\s*(?P<minute>\d{1,2})|(?P<half>時半)|時)?"

    date_time_patterns = [
        rf"(?P<year>20\d{{2}})[./年-](?P<month>\d{{1,2}})[./月-](?P<day>\d{{1,2}})日?"
        rf"(?:\s*[（(]?[月火水木金土日][）)]?)?.{{0,60}}?{clock}",
        rf"(?P<month>\d{{1,2}})[./月-](?P<day>\d{{1,2}})日?"
        rf"(?:\s*[（(]?[月火水木金土日][）)]?)?.{{0,60}}?{clock}",
    ]
    for pattern in date_time_patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        values = match.groupdict()
        hour, minute = _clock_groups(match)
        result = _safe_datetime(
            int(values.get("year") or anchor.year),
            int(values["month"]),
            int(values["day"]),
            hour,
            minute,
        )
        if result is None:
            continue
        return _roll_year_if_needed(result, anchor, bool(values.get("year")))

    relative = re.search(
        rf"(?P<day>本日|今日|今夜|明日|明後日).{{0,50}}?{clock}",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if relative:
        offsets = {"本日": 0, "今日": 0, "今夜": 0, "明日": 1, "明後日": 2}
        day = (anchor + timedelta(days=offsets[relative.group("day")])).date()
        hour, minute = _clock_groups(relative)
        return _safe_datetime(day.year, day.month, day.day, hour, minute)

    weekday_time = re.search(
        rf"(?P<prefix>次(?:の)?|来週(?:の)?|今週(?:の)?|毎週)?\s*(?P<weekday>[月火水木金土日])曜(?:日)?"
        rf".{{0,80}}?{clock}",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if weekday_time:
        day = _weekday_date(anchor, weekday_time.group("weekday"), weekday_time.group("prefix") or "")
        hour, minute = _clock_groups(weekday_time)
        result = _safe_datetime(day.year, day.month, day.day, hour, minute)
        if result and not weekday_time.group("prefix") and result < anchor - timedelta(hours=2):
            result += timedelta(days=7)
        return result

    if not allow_inferred_datetime(normalized):
        return None

    date_only_patterns = [
        r"(?P<year>20\d{2})[./年-](?P<month>\d{1,2})[./月-](?P<day>\d{1,2})日?",
        r"(?P<month>\d{1,2})[./月-](?P<day>\d{1,2})日?",
    ]
    for pattern in date_only_patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        values = match.groupdict()
        result = _safe_datetime(
            int(values.get("year") or anchor.year),
            int(values["month"]),
            int(values["day"]),
            DEFAULT_EVENT_HOUR,
            0,
        )
        if result is None:
            continue
        return _roll_year_if_needed(result, anchor, bool(values.get("year")))

    relative_only = re.search(r"(?:本日|今日|今夜|明日|明後日)", normalized)
    if relative_only:
        token = relative_only.group(0)
        offsets = {"本日": 0, "今日": 0, "今夜": 0, "明日": 1, "明後日": 2}
        day = (anchor + timedelta(days=offsets[token])).date()
        return datetime.combine(day, time(DEFAULT_EVENT_HOUR), tzinfo=JST)

    weekday_only = re.search(
        r"(?P<prefix>次(?:の)?|来週(?:の)?|今週(?:の)?|毎週)?\s*(?P<weekday>[月火水木金土日])曜(?:日)?",
        normalized,
        flags=re.IGNORECASE,
    )
    if weekday_only:
        day = _weekday_date(anchor, weekday_only.group("weekday"), weekday_only.group("prefix") or "")
        return datetime.combine(day, time(DEFAULT_EVENT_HOUR), tzinfo=JST)

    return None


def datetime_is_inferred(text: str) -> bool:
    normalized = normalize_text(text)
    explicit_clock = re.search(
        r"(?:[01]?\d|2[0-9])(?::\d{1,2}|時(?:\d{1,2}分?|半)?)",
        normalized,
    )
    return explicit_clock is None


def structured_classify(text: str) -> tuple[str | None, str | None]:
    from scripts import collect_yahoo_corpus as legacy

    normalized = normalize_text(text)
    if RECAP_RE.search(normalized) or PERSONAL_PLAN_RE.search(normalized):
        return None, "past_event_report"
    if _is_cancelled(normalized):
        return None, "cancelled_or_postponed"
    if OFFLINE_ONLY_RE.search(normalized):
        return None, "not_vrchat"
    if NON_EVENT_NOTICE_RE.search(normalized):
        return None, "missing_event_marker"

    has_schedule = bool(SCHEDULE_RE.search(normalized))
    has_generic_event = bool(GENERIC_EVENT_RE.search(normalized))
    has_action = bool(EVENT_ACTION_RE.search(normalized))
    has_attendance = bool(ATTENDANCE_RE.search(normalized))
    has_access = bool(ACCESS_RE.search(normalized))
    has_broadcast = bool(BROADCAST_RE.search(normalized))
    world_description = bool(WORLD_DESCRIPTION_RE.search(normalized))

    if has_broadcast and not has_access and not has_attendance:
        return None, "missing_event_marker"
    if world_description and not (has_generic_event and has_action and has_schedule):
        return None, "missing_event_marker"

    category, reason = legacy.structured_classify(normalized)
    if reason != "missing_event_marker":
        return category, reason
    if not implementation.VRCHAT_RE.search(normalized):
        return None, "not_vrchat"
    if strong_occurrence(normalized):
        return "event", None
    return None, "missing_event_marker"


def candidate_to_event(
    candidate: dict[str, Any], *, now: datetime, min_retweets: int, x_ids: set[str]
) -> tuple[dict[str, Any] | None, str | None]:
    post_id = str(candidate.get("status_id") or "")
    text = str(candidate.get("text") or "").strip()
    if not implementation.STATUS_ID_RE.fullmatch(post_id):
        return None, "invalid_status_id"
    if post_id in x_ids:
        return None, "duplicate_x_source"
    if len(text) < 12:
        return None, "missing_text"
    if len(text) > 1200 or any(marker in text for marker in ('\\",\\"', '"displayText"', '"rtCount"')):
        return None, "malformed_text"

    category, reason = structured_classify(text)
    if reason:
        return None, reason

    retweets = candidate.get("retweet_count")
    if retweets is None:
        return None, "retweet_count_missing"
    try:
        reposts = int(retweets)
    except (TypeError, ValueError):
        return None, "retweet_count_invalid"
    if reposts < min_retweets:
        return None, "retweet_below_threshold"

    event_at = parse_event_datetime(text, now.astimezone(JST))
    if event_at is None:
        return None, "missing_datetime"
    if event_at > now.astimezone(JST) + timedelta(days=MAX_FUTURE_DAYS):
        return None, "too_far_future"

    inferred = datetime_is_inferred(text)
    author = str(candidate.get("author") or "").strip().lstrip("@")
    tags = ["VRChat", "Yahoo!リアルタイム検索", "機械判定", "リポスト3件以上"]
    if inferred:
        tags.append("日時推定")
    event = {
        "source_id": f"yahoo:x:{post_id}",
        "title": implementation.title_from_text(text, str(category)),
        "starts_at": implementation.utc_text(event_at),
        "organizer": f"@{author}" if author else None,
        "location": "オンライン" if category == "recruitment_deadline" else "VRChat",
        "description": re.sub(r"\s+", " ", text).strip(),
        "url": candidate.get("url") or f"https://x.com/i/web/status/{post_id}",
        "category": category,
        "tags": tags,
        "confidence": 0.78 if inferred else 0.9,
        "review_required": False,
    }
    return {key: value for key, value in event.items() if value is not None}, None
