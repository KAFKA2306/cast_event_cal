from datetime import datetime, timedelta, timezone
from unittest import TestCase

from scripts.check_production_refresh_liveness import evaluate


NOW = datetime(2026, 10, 24, 0, 0, tzinfo=timezone.utc)


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
