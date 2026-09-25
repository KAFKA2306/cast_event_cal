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


def test_durable_status_job_runs_after_success_or_failure() -> None:
    text = workflow_text()
    assert "  status:\n" in text
    assert "    needs: build\n" in text
    assert "    if: ${{ always() }}\n" in text
    assert 'python scripts/build_system_status.py --refresh-result "${{ needs.build.result }}" --max-age-minutes 180' in text
    assert "git add public/status.json" in text
