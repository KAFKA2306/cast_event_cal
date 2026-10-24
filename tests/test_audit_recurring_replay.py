from datetime import UTC, datetime

from scripts.audit_recurring_replay import replay

ANCHOR = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


def candidate(text: str, **extra: str) -> dict[str, str]:
    return {"datetime_reason": "recurring_event", "text": text, **extra}


def test_unresolved_missing_provenance_does_not_create_unsafe_promotion():
    report = replay(
        [candidate("毎週土曜日に集会を開催します")],
        set(),
        now=ANCHOR,
    )

    assert report["provenance_missing"] == 1
    assert report["promotions_without_provenance"] == 0


def test_resolved_new_occurrence_without_provenance_is_unsafe_promotion():
    report = replay(
        [candidate("毎週金曜日 22:00から集会を開催します")],
        set(),
        now=ANCHOR,
    )

    assert report["materialized_future_occurrences"] >= 1
    assert report["promotions_without_provenance"] >= 1


def test_resolved_new_occurrence_with_provenance_is_safe():
    report = replay(
        [
            candidate(
                "毎週金曜日 22:00から集会を開催します",
                status_id="123",
                url="https://example.invalid/event/123",
            )
        ],
        set(),
        now=ANCHOR,
    )

    assert report["materialized_future_occurrences"] >= 1
    assert report["promotions_without_provenance"] == 0
