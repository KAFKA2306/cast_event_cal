import copy

from scripts.gate_yahoo_llm_review_queue import semantic_hash


def queue() -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": "2026-09-27T00:00:00Z",
        "policy": {"resolved_items_are_excluded": True},
        "pending_count": 2,
        "items": [
            {"status_id": "2", "review_kind": "ambiguous_rejection", "priority": "normal", "first_queued_at": "a", "last_queued_at": "b"},
            {"status_id": "1", "review_kind": "possible_false_positive", "priority": "high", "first_queued_at": "a", "last_queued_at": "b"},
        ],
    }


def test_timestamp_and_input_order_do_not_change_identity() -> None:
    before = queue()
    after = copy.deepcopy(before)
    after["generated_at"] = "2026-09-28T00:00:00Z"
    after["items"].reverse()
    for item in after["items"]:
        item["last_queued_at"] = "later"
    assert semantic_hash(before) == semantic_hash(after)


def test_priority_change_is_semantic() -> None:
    before = queue()
    after = copy.deepcopy(before)
    after["items"][0]["priority"] = "high"
    assert semantic_hash(before) != semantic_hash(after)


def test_resolved_item_removal_is_semantic() -> None:
    before = queue()
    after = copy.deepcopy(before)
    after["items"] = after["items"][1:]
    after["pending_count"] = 1
    assert semantic_hash(before) != semantic_hash(after)


def test_malformed_queue_fails_closed() -> None:
    malformed = queue()
    malformed["items"] = [{"priority": "high"}]
    try:
        semantic_hash(malformed)
    except ValueError:
        return
    raise AssertionError("malformed queue must fail closed")
