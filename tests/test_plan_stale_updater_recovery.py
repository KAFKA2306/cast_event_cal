from datetime import UTC, datetime, timedelta

from scripts.plan_stale_updater_recovery import plan_recovery


NOW = datetime(2026, 11, 3, 0, 2, tzinfo=UTC)


def run_at(minutes_ago: int, *, event: str = "schedule", status: str = "completed") -> dict:
    return {
        "id": minutes_ago,
        "event": event,
        "status": status,
        "created_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
    }


def decide(state: str, runs: list[dict]) -> dict:
    return plan_recovery(
        {"state": state}, runs, checked_at=NOW, cooldown_minutes=150
    )


def test_old_failed_updater_can_recover_but_recent_attempt_cannot():
    assert decide("failed", [run_at(200)])["dispatch"] is True
    assert decide("failed", [run_at(30)])["reason"] == "recent_updater_attempt"
    assert decide("late", [run_at(200), run_at(30)])["reason"] == "recent_updater_attempt"


def test_late_updater_with_no_recent_attempt_can_recover():
    assert decide("late", [run_at(169, event="workflow_dispatch")])["dispatch"] is True


def test_recent_manual_dispatch_prevents_repeat_recovery():
    decision = decide("late", [run_at(60, event="workflow_dispatch")])
    assert decision["dispatch"] is False
    assert decision["reason"] == "manual_dispatch_cooldown"


def test_daily_budget_blocks_older_manual_dispatches():
    decision = decide(
        "late",
        [run_at(250, event="workflow_dispatch"), run_at(350, event="workflow_dispatch")],
    )
    assert decision["dispatch"] is False
    assert decision["reason"] == "daily_dispatch_budget_exhausted"


def test_active_updater_prevents_concurrent_recovery():
    decision = decide("failed", [run_at(5, status="in_progress"), run_at(200)])
    assert decision["reason"] == "updater_active_or_unknown"


def test_incomplete_24h_history_fails_closed():
    runs = [run_at(300 + i) for i in range(100)]
    assert decide("late", runs)["reason"] == "run_history_incomplete_for_daily_budget"


def test_missing_or_invalid_control_plane_fails_closed():
    assert decide("late", [])["dispatch"] is False
    invalid = [{"status": "completed", "created_at": "invalid"}]
    assert decide("failed", invalid)["dispatch"] is False
    assert decide("unknown", [run_at(200)])["dispatch"] is False
