import json
from datetime import UTC, datetime

import pytest

from scripts.fetch_yahoo_realtime import (
    candidate_to_event,
    extract_candidates,
    merge_cache,
    parse_event_datetime,
    validate_search_url,
)


def structured_page(posts: list[dict[str, object]]) -> str:
    payload = json.dumps({"props": {"posts": posts}}, ensure_ascii=False)
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{payload}</script></body></html>'


def test_structured_parser_accepts_explicit_event_and_rejects_product_only():
    page = structured_page(
        [
            {
                "id": "1234567890123456789",
                "displayText": "【VRC俺確】2026/8/7 22:00 VRChatイベントを開催。参加方法は当日Join",
                "screenName": "host",
                "rtCount": 5,
                "url": "https://x.com/host/status/1234567890123456789",
            },
            {
                "id": "2234567890123456789",
                "displayText": "8/8 20:00 VRChat衣装をBOOTHで販売開始",
                "screenName": "shop",
                "rtCount": 20,
                "url": "https://x.com/shop/status/2234567890123456789",
            },
        ]
    )
    candidates = {item["status_id"]: item for item in extract_candidates(page)}
    now = datetime(2026, 8, 2, tzinfo=UTC)

    accepted, reason = candidate_to_event(
        candidates["1234567890123456789"], now=now, min_retweets=3, x_ids=set()
    )
    assert reason is None
    assert accepted is not None
    assert accepted["starts_at"] == "2026-08-07T13:00:00Z"
    assert accepted["organizer"] == "@host"

    rejected, reason = candidate_to_event(
        candidates["2234567890123456789"], now=now, min_retweets=3, x_ids=set()
    )
    assert rejected is None
    assert reason == "product_only"


def test_parser_requires_metrics_and_rejects_x_duplicate():
    base = {
        "status_id": "1234567890123456789",
        "url": "https://x.com/host/status/1234567890123456789",
        "text": "2026/8/7 22:00 VRChatイベントを開催",
        "author": "host",
        "retweet_count": None,
    }
    now = datetime(2026, 8, 2, tzinfo=UTC)
    assert candidate_to_event(base, now=now, min_retweets=3, x_ids=set())[1] == "retweet_count_missing"

    duplicate = dict(base, retweet_count=10)
    assert candidate_to_event(
        duplicate, now=now, min_retweets=3, x_ids={"1234567890123456789"}
    )[1] == "duplicate_x_source"


def test_parent_json_blob_is_rejected_as_malformed():
    malformed = {
        "status_id": "3234567890123456789",
        "url": "https://x.com/i/web/status/3234567890123456789",
        "text": '2026/8/7 22:00 VRChatイベントを開催 {"displayText":"別投稿","rtCount":10}',
        "author": None,
        "retweet_count": 10,
    }
    assert candidate_to_event(
        malformed, now=datetime(2026, 8, 2, tzinfo=UTC), min_retweets=3, x_ids=set()
    )[1] == "malformed_text"


def test_relative_datetime_and_cache_expiration():
    anchor = datetime(2026, 8, 2, 15, 0, tzinfo=UTC)
    parsed = parse_event_datetime("本日 23:00 VRChat集会を開催", anchor.astimezone())
    assert parsed is not None

    existing = [
        {"source_id": "old", "starts_at": "2026-07-01T00:00:00Z", "title": "expired"},
        {"source_id": "future", "starts_at": "2026-08-08T00:00:00Z", "title": "cached"},
    ]
    fresh = [{"source_id": "new", "starts_at": "2026-08-09T00:00:00Z", "title": "fresh"}]
    merged = merge_cache(existing, fresh, datetime(2026, 8, 2, tzinfo=UTC))
    assert {item["source_id"] for item in merged} == {"future", "new"}


def test_search_url_is_pinned_to_yahoo_realtime():
    validate_search_url("https://search.yahoo.co.jp/realtime/search?ei=UTF-8&p=VRChat")
    with pytest.raises(ValueError):
        validate_search_url("https://example.com/realtime/search?p=VRChat")
