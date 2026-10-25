from pathlib import Path


WORKFLOW = Path(".github/workflows/update-calendar-v2.yml")


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_hourly_schedule_is_an_actual_yaml_entry() -> None:
    lines = [line.rstrip() for line in workflow_text().splitlines()]
    assert "    - cron: '17 * * * *'" in lines
    assert not any("\\n    - cron:" in line for line in lines)


def test_required_production_gates_run_before_commit() -> None:
    text = workflow_text()
    required = [
        "python scripts/audit_public_feed.py public/events.json",
        "python scripts/validate_update_snapshot.py",
        "python scripts/write_snapshot_identity.py --check public/snapshot.json",
        "python scripts/audit_freshness.py --max-age-minutes 180",
    ]
    commit_marker = "- name: Commit generated data safely"
    assert commit_marker in text
    commit_index = text.index(commit_marker)
    for command in required:
        assert command in text
        assert text.index(command) < commit_index


def test_failed_refresh_writes_only_durable_status_after_publish():
    text = workflow_text()
    assert "  status_on_failure:\n" in text
    status_job = text.split("  status_on_failure:\n", 1)[1]
    assert "needs: [build, publish]" in status_job
    assert "always()" in status_job
    assert "needs.publish.result != 'success'" in status_job
    assert "--refresh-result failure" in status_job
    assert "git add public/status.json" in status_job
    assert "git add public/" not in status_job
