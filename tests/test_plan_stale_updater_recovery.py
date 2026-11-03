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


def test_late_updater_with_no_active_or_recent_manual_run_can_recover():
    assert decide("late", [run_at(169, event="workflow_dispatch")])["dispatch"] is True


def test_recent_manual_dispatch_prevents_repeat_recovery():
    decision = decide("late", [run_at(60, event="workflow_dispatch")])
    assert decision["dispatch"] is False
    assert decision["reason"] == "manual_dispatch_cooldown"


def test_active_updater_prevents_concurrent_recovery():
    decision = decide("late", [run_at(5, status="in_progress"), run_at(200)])
    assert decision["dispatch"] is False
    assert decision["reason"] == "updater_active_or_unknown"


def test_failed_updater_is_not_misclassified_as_schedule_delay():
    assert decide("failed", [run_at(200)])["dispatch"] is False


def test_missing_or_invalid_control_plane_fails_closed():
    assert decide("late", [])["dispatch"] is False
    assert decide("late", [{"status": "completed", "created_at": "invalid"}])["dispatch"] is False
