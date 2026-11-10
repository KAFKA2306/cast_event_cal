from datetime import UTC, datetime, timedelta
from unittest import TestCase

from scripts.check_production_refresh_liveness import evaluate, recovery_decision


NOW = datetime(2026, 10, 24, 0, 0, tzinfo=UTC)


def run(minutes_ago, *, conclusion="success", branch="main", url="https://github.com/test/runs/1"):
    return {
        "head_branch": branch,
        "conclusion": conclusion,
        "updated_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
        "html_url": url,
    }


class LivenessTests(TestCase):
    def test_recent_success_is_healthy(self):
        healthy, _ = evaluate([run(30)], NOW)
        self.assertTrue(healthy)

    def test_old_success_fails(self):
        healthy, message = evaluate([run(181)], NOW)
        self.assertFalse(healthy)
        self.assertIn("181 minutes", message)

    def test_no_success_fails(self):
        healthy, message = evaluate([run(1, conclusion="failure")], NOW)
        self.assertFalse(healthy)
        self.assertIn("no successful", message)

    def test_wrong_branch_cannot_mask_outage(self):
        healthy, _ = evaluate([run(1, branch="feature"), run(200)], NOW)
        self.assertFalse(healthy)

    def test_newer_failure_does_not_erase_recent_success(self):
        healthy, _ = evaluate([run(1, conclusion="failure"), run(40)], NOW)
        self.assertTrue(healthy)

    def test_future_timestamp_fails_closed(self):
        healthy, _ = evaluate([run(-2)], NOW)
        self.assertFalse(healthy)

    def test_bad_timestamp_cannot_mask_outage(self):
        bad = run(1)
        bad["updated_at"] = "not-a-timestamp"
        healthy, _ = evaluate([bad, run(200)], NOW)
        self.assertFalse(healthy)

    def test_recovery_is_allowed_after_stale_scheduled_run(self):
        stale = run(240)
        stale.update({"created_at": (NOW - timedelta(minutes=240)).isoformat(), "event": "schedule", "status": "completed"})
        allowed, _ = recovery_decision([stale], NOW)
        self.assertTrue(allowed)

    def test_recent_attempt_prevents_duplicate_dispatch(self):
        recent = run(40, conclusion="failure")
        recent.update({"created_at": (NOW - timedelta(minutes=40)).isoformat(), "event": "schedule", "status": "completed"})
        allowed, message = recovery_decision([recent], NOW)
        self.assertFalse(allowed)
        self.assertIn("recently", message)

    def test_active_run_prevents_racing_recovery(self):
        active = run(110, conclusion=None)
        active.update({"created_at": (NOW - timedelta(minutes=110)).isoformat(), "event": "schedule", "status": "in_progress"})
        allowed, message = recovery_decision([active], NOW)
        self.assertFalse(allowed)
        self.assertIn("still running", message)

    def test_daily_recovery_budget_prevents_retry_loop(self):
        runs = []
        for age in (110, 180):
            row = run(age, conclusion="failure")
            row.update({"created_at": (NOW - timedelta(minutes=age)).isoformat(), "event": "workflow_dispatch", "status": "completed"})
            runs.append(row)
        allowed, message = recovery_decision(runs, NOW)
        self.assertFalse(allowed)
        self.assertIn("budget", message)
