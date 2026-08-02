from datetime import UTC, datetime

from scripts.collect_yahoo_corpus import (
    NEXT_MONTH_CONFLICT_RE,
    build_query_plan,
    configure_classifier,
    merge_provenance,
    read_json,
    refined_candidate_to_event,
)


def candidate(text: str, *, retweets: int = 10) -> dict[str, object]:
    return {
        "status_id": "1234567890123456789",
        "url": "https://x.com/host/status/1234567890123456789",
        "text": text,
        "author": "host",
        "retweet_count": retweets,
    }


def test_query_plan_is_broad_unique_and_target_oriented():
    config = read_json(__import__("pathlib").Path("config/yahoo_query_terms.json"), {})
    plan = build_query_plan(config)
    assert len(plan) >= 120
    assert len({item["query"].casefold() for item in plan}) == len(plan)
    assert {item["group"] for item in plan} >= {
        "core",
        "access",
        "venues",
        "activities",
        "communities",
        "recruitment",
        "commerce_noise",
        "temporal_audit",
    }


def test_private_birthday_instance_requires_participation_method():
    configure_classifier()
    event, reason = refined_candidate_to_event(
        candidate("2026/8/7 22:00 VRC誕生日インスタンスを開催します。ぜひお越しください"),
        now=datetime(2026, 8, 2, tzinfo=UTC),
        min_retweets=3,
        x_ids=set(),
    )
    assert event is None
    assert reason == "missing_participation_method"

    event, reason = refined_candidate_to_event(
        candidate("2026/8/7 22:00 VRC誕生日インスタンスを開催。参加方法は主催へフレンド申請後にJOIN"),
        now=datetime(2026, 8, 2, tzinfo=UTC),
        min_retweets=3,
        x_ids=set(),
    )
    assert reason is None
    assert event is not None


def test_giveaway_with_generic_event_word_stays_rejected():
    configure_classifier()
    event, reason = refined_candidate_to_event(
        candidate("2026/8/7 22:00 VRChat向けアバター販売記念プレゼントキャンペーン開催中。フォロー＆RPで応募"),
        now=datetime(2026, 8, 2, tzinfo=UTC),
        min_retweets=3,
        x_ids=set(),
    )
    assert event is None
    assert reason == "giveaway_only"


def test_conflicting_next_event_month_is_rejected():
    text = "2024年1月VRC同期会。次回の同期会は3月合同同期会！日時：2026/08/23 21:00 VRChatで開催"
    match = NEXT_MONTH_CONFLICT_RE.search(text)
    assert match is not None
    assert match.group("label_month") == "3"
    assert match.group("date_month") == "08"
    event, reason = refined_candidate_to_event(
        candidate(text),
        now=datetime(2026, 8, 2, tzinfo=UTC),
        min_retweets=3,
        x_ids=set(),
    )
    assert event is None
    assert reason == "conflicting_date_context"


def test_provenance_merge_preserves_queries_and_retweet_peak():
    merged = [
        {
            "status_id": "1234567890123456789",
            "url": "https://x.com/host/status/1234567890123456789",
            "text": "8/7 22:00 VRCイベント開催。参加方法はJOIN",
            "author": "host",
            "retweet_count": 9,
            "first_seen_at": "2026-08-01T07:00:00Z",
            "last_seen_at": "2026-08-02T07:00:00Z",
            "last_decision": "accepted",
            "last_reason": None,
        }
    ]
    existing = [
        {
            "status_id": "1234567890123456789",
            "retweet_count": 5,
            "max_retweet_count": 5,
            "first_seen_at": "2026-08-01T07:00:00Z",
            "last_seen_at": "2026-08-01T07:00:00Z",
            "query_keys": ["core-001"],
            "query_groups": ["core"],
            "query_terms": ["開催"],
            "observation_count": 1,
        }
    ]
    observed = [
        {
            "status_id": "1234567890123456789",
            "retweet_count": 9,
            "query_keys": ["access-001"],
            "query_groups": ["access"],
            "query_terms": ["JOIN"],
        }
    ]
    rows = merge_provenance(
        merged,
        existing,
        observed,
        datetime(2026, 8, 2, 7, 0, tzinfo=UTC),
    )
    assert rows[0]["first_seen_at"] == "2026-08-01T07:00:00Z"
    assert rows[0]["last_seen_at"] == "2026-08-02T07:00:00Z"
    assert rows[0]["observation_count"] == 2
    assert rows[0]["max_retweet_count"] == 9
    assert rows[0]["query_keys"] == ["access-001", "core-001"]
