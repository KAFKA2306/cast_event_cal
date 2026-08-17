import json
from datetime import UTC, datetime

import pytest

from scripts.fetch_yahoo_realtime import (
    candidate_to_event,
    classify,
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


def test_yahoo_boundary_markers_are_removed_but_event_start_text_is_preserved():
    page = structured_page(
        [
            {
                "id": "5234567890123456789",
                "displayText": (
                    "START 2026/8/7 22:00 VRChatイベントを開催。"
                    "OPEN 21:50 / START 22:00 END"
                ),
                "screenName": "host",
                "rtCount": 5,
                "url": "https://x.com/host/status/5234567890123456789",
            }
        ]
    )
    candidate = extract_candidates(page)[0]
    assert candidate["text"].startswith("2026/8/7")
    assert "START 22:00" in candidate["text"]
    assert not candidate["text"].endswith(" END")

    accepted, reason = candidate_to_event(
        candidate, now=datetime(2026, 8, 2, tzinfo=UTC), min_retweets=3, x_ids=set()
    )
    assert reason is None
    assert accepted is not None
    assert not accepted["title"].startswith("START ")
    assert not accepted["description"].startswith("START ")
    assert "START 22:00" in accepted["description"]


def test_merge_cache_cleans_legacy_yahoo_boundary_markers():
    existing = [
        {
            "source_id": "yahoo:x:6234567890123456789",
            "starts_at": "2026-08-08T12:00:00Z",
            "title": "START cached event",
            "description": "START 8/8 21:00 VRChatイベントを開催。参加方法はJoin END",
        }
    ]
    merged = merge_cache(existing, [], datetime(2026, 8, 2, tzinfo=UTC))
    assert len(merged) == 1
    assert merged[0]["title"] == "cached event"
    assert merged[0]["description"] == "8/8 21:00 VRChatイベントを開催。参加方法はJoin"


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


def test_commerce_and_giveaway_override_generic_date_words():
    assert classify("本日20:30 Patreon記事を公開 VRChat用キーチェーン") == (None, "product_only")
    assert classify("8/5 21:00 VRChat衣装プレゼント 応募締切") == (None, "giveaway_only")
    assert classify("8/9 23:59 VRChatアバターテスター応募締切") == (
        "recruitment_deadline",
        None,
    )


def test_relative_datetime_and_cache_expiration_and_revalidation():
    anchor = datetime(2026, 8, 2, 15, 0, tzinfo=UTC)
    parsed = parse_event_datetime("本日 23:00 VRChat集会を開催", anchor.astimezone())
    assert parsed is not None

    existing = [
        {
            "source_id": "yahoo:x:1111111111111111111",
            "starts_at": "2026-07-01T00:00:00Z",
            "title": "expired",
            "description": "7/1 21:00 VRChatイベントを開催",
        },
        {
            "source_id": "yahoo:x:2222222222222222222",
            "starts_at": "2026-08-08T00:00:00Z",
            "title": "commerce",
            "description": "8/8 09:00 VRChat衣装をBOOTHで販売開始",
        },
        {
            "source_id": "yahoo:x:3333333333333333333",
            "starts_at": "2026-08-08T12:00:00Z",
            "title": "cached",
            "description": "8/8 21:00 VRChatイベントを開催。参加方法はJoin",
        },
    ]
    fresh = [
        {
            "source_id": "yahoo:x:4444444444444444444",
            "starts_at": "2026-08-09T12:00:00Z",
            "title": "fresh",
            "description": "8/9 21:00 VRChat集会を開催。グループインスタンスへJoin",
        }
    ]
    merged = merge_cache(existing, fresh, datetime(2026, 8, 2, tzinfo=UTC))
    assert {item["source_id"] for item in merged} == {
        "yahoo:x:3333333333333333333",
        "yahoo:x:4444444444444444444",
    }


def test_search_url_is_pinned_to_yahoo_realtime():
    validate_search_url("https://search.yahoo.co.jp/realtime/search?ei=UTF-8&p=VRChat")
    with pytest.raises(ValueError):
        validate_search_url("https://example.com/realtime/search?p=VRChat")
