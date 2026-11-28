import json
from datetime import UTC, datetime

import pytest

from scripts import audit_updater_liveness

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


@pytest.mark.parametrize(("age", "expected"), [(240, 0), (360, 0), (361, 1)])
def test_late_exit_code_respects_extreme_staleness(tmp_path, monkeypatch, age, expected):
    checked_at = NOW
    success_at = checked_at.timestamp() - age * 60
    created_at = datetime.fromtimestamp(success_at, UTC).isoformat()
    input_path = tmp_path / "runs.json"
    input_path.write_text(json.dumps({"runs": [run(1, created_at)], "jobs_by_run": {"1": [{"id": 10}]}}))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"late_after_minutes": 150, "extreme_stale_after_minutes": 360}))
    output_path = tmp_path / "out.json"
    monkeypatch.setattr("sys.argv", ["audit_updater_liveness", "--input", str(input_path), "--config", str(config_path), "--output", str(output_path), "--checked-at", NOW.isoformat()])

    assert audit_updater_liveness.main() == expected


@pytest.mark.parametrize("payload", [{"runs": [], "jobs_by_run": {}}, {"runs": [run(1, "2026-09-28T09:00:00Z", "failure")], "jobs_by_run": {"1": [{"id": 10}]}}])
def test_unknown_or_failed_exit_nonzero(tmp_path, monkeypatch, payload):
    input_path = tmp_path / "runs.json"
    input_path.write_text(json.dumps(payload))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"late_after_minutes": 150, "extreme_stale_after_minutes": 360}))
    monkeypatch.setattr("sys.argv", ["audit_updater_liveness", "--input", str(input_path), "--config", str(config_path), "--output", str(tmp_path / "out.json"), "--checked-at", NOW.isoformat()])

    assert audit_updater_liveness.main() == 1
