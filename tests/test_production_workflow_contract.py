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
    assert not any(line.strip() in {"git add public/", "git add public"} for line in status_job.splitlines())


def test_base_drift_rebuild_is_bounded_and_never_publishes_stale_output() -> None:
    text = workflow_text()
    publish = text.split("  publish:\\n", 1)[1].split("  status_on_failure:\\n", 1)[0]
    recovery = text.split("  status_on_failure:\\n", 1)[1]

    # A changed main must fail the original publisher before any commit.
    assert '"base_changed_after_validation:"' in publish
    assert 'echo \'base_changed=true\' >> "$GITHUB_OUTPUT"' in publish
    assert 'exit "$guard_status"' in publish
    assert publish.index("exit \\"$guard_status\\"") < publish.index("Commit generated data safely")

    # Rebuild from a fresh main checkout, at most once per failed run.
    assert "needs.publish.outputs.base_changed == 'true'" in recovery
    assert "inputs.recovery_attempt != '1'" in recovery
    assert "needs.build.result == 'success'" in recovery
    assert recovery.count("gh workflow run update-calendar-v2.yml --ref main -f recovery_attempt=1") == 1
    assert recovery.index("git push origin HEAD:main") < recovery.index("Rebuild once from current main")
