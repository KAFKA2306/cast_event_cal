from __future__ import annotations

import pytest

from scripts.replay_yahoo_datetime_recovery import assert_targets


def report(*, promoted: int, durable: int) -> dict[str, object]:
    return {
        "existing_accepted_lost": 0,
        "lost_status_ids": [],
        "promoted_without_resolution_evidence": 0,
        "promoted_other_without_resolution_evidence": [],
        "unreviewed_other_promotions": [],
        "review_reason_mismatches": [],
        "reviewed_false_promoted": [],
        "newly_promoted": promoted,
        "promoted_from_missing_datetime": promoted,
        "promoted_from_other_reasons": 0,
        "accepted_with_resolution_evidence": durable,
    }


def test_replay_gate_accepts_initial_migration_target() -> None:
    assert_targets(report(promoted=50, durable=50), 50)


def test_replay_gate_accepts_steady_state_after_promotions_are_persisted() -> None:
    assert_targets(report(promoted=0, durable=190), 50)


def test_replay_gate_accepts_small_increment_after_durable_floor_is_met() -> None:
    assert_targets(report(promoted=3, durable=185), 50)


def test_replay_gate_rejects_steady_state_resolution_regression() -> None:
    with pytest.raises(AssertionError):
        assert_targets(report(promoted=0, durable=49), 50)
