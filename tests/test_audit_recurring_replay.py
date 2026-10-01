from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.audit_recurring_replay import build

JST = ZoneInfo("Asia/Tokyo")
ANCHOR = datetime(2026, 10, 1, 8, 0, tzinfo=JST)


def test_unresolved_row_with_incomplete_provenance_does_not_block_publication():
    payload = build(
        [{"text": "毎週土曜日に集会を開催します"}],
        public_starts=set(),
        after=ANCHOR,
        count=1,
    )

    assert payload["provenance_missing"] == 1
    assert payload["promotions_without_provenance"] == 0
    assert payload["materialized_future_occurrences"] == 0
    assert payload["publication_gate_passed"] is True


def test_new_occurrence_without_provenance_blocks_publication():
    payload = build(
        [{"text": "毎週金曜日 22:00から集会を開催します"}],
        public_starts=set(),
        after=ANCHOR,
        count=1,
    )

    assert payload["materialized_future_occurrences"] == 1
    assert payload["promotions_without_provenance"] == 1
    assert payload["publication_gate_passed"] is False


def test_new_occurrence_with_complete_provenance_passes_publication_gate():
    payload = build(
        [
            {
                "status_id": "123",
                "url": "https://example.invalid/event/123",
                "text": "毎週金曜日 22:00から集会を開催します",
            }
        ],
        public_starts=set(),
        after=ANCHOR,
        count=1,
    )

    assert payload["materialized_future_occurrences"] == 1
    assert payload["promotions_without_provenance"] == 0
    assert payload["publication_gate_passed"] is True
