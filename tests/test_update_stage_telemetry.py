from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import finalize_update_telemetry, run_stage


def test_fingerprint_is_stable_and_changes_with_content(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    source.write_text("alpha", encoding="utf-8")
    first = run_stage.fingerprint_paths(tmp_path, [str(source)])
    second = run_stage.fingerprint_paths(tmp_path, [str(source)])
    assert first == second

    source.write_text("beta", encoding="utf-8")
    changed = run_stage.fingerprint_paths(tmp_path, [str(source)])
    assert changed["sha256"] != first["sha256"]

    package = tmp_path / "package"
    package.mkdir()
    (package / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    stable = run_stage.fingerprint_paths(tmp_path, [str(package)])
    cache = package / "__pycache__"
    cache.mkdir()
    (cache / "module.cpython-312.pyc").write_bytes(b"runtime-only")
    assert run_stage.fingerprint_paths(tmp_path, [str(package)]) == stable


def test_stage_records_output_change_and_propagates_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    report = tmp_path / "telemetry.jsonl"
    code = "from pathlib import Path; Path('output.txt').write_text('created', encoding='utf-8')"
    exit_code = run_stage.main(
        [
            "--report",
            str(report),
            "--name",
            "fixture",
            "--kind",
            "projection",
            "--output",
            "output.txt",
            "--",
            sys.executable,
            "-c",
            code,
        ]
    )
    assert exit_code == 0
    record = json.loads(report.read_text(encoding="utf-8"))
    assert record["status"] == "executed"
    assert record["output_changed"] is True
    assert record["output_after"]["file_count"] == 1

    failed = run_stage.main(
        [
            "--report",
            str(report),
            "--name",
            "failure",
            "--kind",
            "validation",
            "--",
            sys.executable,
            "-c",
            "raise SystemExit(7)",
        ]
    )
    assert failed == 7
    records = [json.loads(line) for line in report.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["status"] == "failed"
    assert records[-1]["return_code"] == 7


def test_finalize_reports_git_churn_and_stage_totals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    tracked = root / "tracked.txt"
    tracked.write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, stdout=subprocess.PIPE)
    tracked.write_text("after\n", encoding="utf-8")

    report = tmp_path / "telemetry.jsonl"
    report.write_text(
        json.dumps(
            {
                "stage": "one",
                "kind": "projection",
                "status": "executed",
                "duration_seconds": 1.25,
                "started_at": "2026-09-22T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(root)
    monkeypatch.setenv("UPDATE_RUN_STARTED_AT", "2026-09-22T00:00:00Z")
    summary = finalize_update_telemetry.summarize(finalize_update_telemetry.read_records(report), root)
    assert summary["stages"]["count"] == 1
    assert summary["stages"]["kind_seconds"]["projection"] == 1.25
    assert summary["git"]["changed_file_count"] == 1
    assert summary["git"]["git_patch_bytes"] > 0


def test_network_measurements_capture_reported_costs(tmp_path: Path) -> None:
    health = tmp_path / "health.json"
    health.write_text(
        json.dumps(
            {
                "queries_attempted": 22,
                "queries_succeeded": 22,
                "queries_failed": 0,
                "raw_candidate_count": 350,
            }
        ),
        encoding="utf-8",
    )
    measurements = run_stage.json_measurements(tmp_path, ["health.json"])
    assert measurements["health.json"]["reported_request_count"] == 22
    assert measurements["health.json"]["reported_fetched_records"] == 350

    aggregate = finalize_update_telemetry.network_metrics(
        [
            {
                "kind": "network",
                "measurements_after": measurements,
            }
        ]
    )
    assert aggregate["reported_request_count"] == 22
    assert aggregate["reported_fetched_records"] == 350
