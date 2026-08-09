from datetime import UTC, datetime

from scripts.build_yahoo_llm_review_queue import build_queue, needs_review


def test_needs_review_keeps_only_ambiguous_cases() -> None:
    assert needs_review({"last_reason": "conflicting_date_context", "retweet_count": 0})
    assert needs_review({"last_reason": "missing_datetime", "retweet_count": 3})
    assert not needs_review({"last_reason": "missing_datetime", "retweet_count": 2})
    assert not needs_review({"last_reason": "product_only", "retweet_count": 100})


def test_build_queue_deduplicates_and_excludes_resolved() -> None:
    now = datetime(2026, 8, 9, 5, 0, tzinfo=UTC)
    history = [
        {
            "status_id": "1",
            "url": "https://x.com/example/status/1",
            "text": "VRChat event maybe tonight",
            "last_decision": "rejected",
            "last_reason": "missing_datetime",
            "retweet_count": 5,
        },
        {
            "status_id": "2",
            "url": "https://x.com/example/status/2",
            "text": "VRChat product",
            "last_decision": "rejected",
            "last_reason": "product_only",
            "retweet_count": 50,
        },
        {
            "status_id": "3",
            "url": "https://x.com/example/status/3",
            "text": "VRChat unclear participation",
            "last_decision": "rejected",
            "last_reason": "missing_participation_method",
            "retweet_count": 0,
        },
    ]
    items = build_queue(
        history,
        [],
        resolved_ids={"3"},
        previous_items={},
        now=now,
    )
    assert [item["status_id"] for item in items] == ["1"]
    assert items[0]["review_kind"] == "ambiguous_rejection"


def test_suspicious_accepted_enters_high_priority_queue() -> None:
    now = datetime(2026, 8, 9, 5, 0, tzinfo=UTC)
    history = [
        {
            "status_id": "10",
            "url": "https://x.com/example/status/10",
            "text": "VRChat event and shop announcement",
            "last_decision": "accepted",
            "last_reason": None,
            "retweet_count": 1,
        }
    ]
    suspicious = [{"status_id": "10"}]
    items = build_queue(
        history,
        suspicious,
        resolved_ids=set(),
        previous_items={},
        now=now,
    )
    assert len(items) == 1
    assert items[0]["machine_decision"] == "accepted"
    assert items[0]["review_kind"] == "possible_false_positive"
    assert items[0]["priority"] == "high"
