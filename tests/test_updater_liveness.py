from datetime import UTC, datetime

from scripts.audit_updater_liveness import evaluate

NOW = datetime(2026, 9, 28, 10, 0, tzinfo=UTC)


def run(run_id, created_at, conclusion="success", status="completed"):
    return {"id": run_id, "created_at": created_at, "status": status, "conclusion": conclusion}


def check(runs, jobs, state, age=None):
    result = evaluate({"runs": runs, "jobs_by_run": jobs}, checked_at=NOW, late_after_minutes=150)
    assert result["state"] == state
    if age is not None:
        assert result["age_minutes"] == age
    return result


def test_recent_success_is_healthy_even_if_source_artifact_would_be_stale():
    result = check([run(1, "2026-09-28T09:00:00Z")], {"1": [{"id": 10}]}, "healthy", 60.0)
    assert result["latest_success_at"] == "2026-09-28T09:00:00Z"


def test_recent_failure_wins_over_older_success():
    check(
        [run(2, "2026-09-28T09:30:00Z", "failure"), run(1, "2026-09-28T09:00:00Z")],
        {"2": [{"id": 20}]},
        "failed",
        60.0,
    )


def test_zero_job_completed_run_is_failed():
    check([run(2, "2026-09-28T09:30:00Z", "failure")], {"2": []}, "failed")


def test_old_success_is_late():
    check([run(1, "2026-09-28T06:00:00Z")], {"1": [{"id": 10}]}, "late", 240.0)


def test_missing_or_unreadable_authority_is_unknown_not_healthy():
    check([], {}, "unknown")
