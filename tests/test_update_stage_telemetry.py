from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import finalize_update_telemetry, run_stage


def test_fingerprint_is_stable_and_ignores_runtime_cache(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"; source.write_text("alpha", encoding="utf-8")
    first = run_stage.fingerprint_paths(tmp_path, [str(source)])
    assert run_stage.fingerprint_paths(tmp_path, [str(source)]) == first
    source.write_text("beta", encoding="utf-8"); assert run_stage.fingerprint_paths(tmp_path, [str(source)])["sha256"] != first["sha256"]
    package = tmp_path / "package"; package.mkdir(); (package / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    stable = run_stage.fingerprint_paths(tmp_path, [str(package)]); cache = package / "__pycache__"; cache.mkdir(); (cache / "module.pyc").write_bytes(b"runtime")
    assert run_stage.fingerprint_paths(tmp_path, [str(package)]) == stable


def test_stage_records_output_change_and_propagates_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path); report = tmp_path / "telemetry.jsonl"
    assert run_stage.main(["--report", str(report), "--name", "fixture", "--kind", "projection", "--output", "output.txt", "--", sys.executable, "-c", "from pathlib import Path; Path('output.txt').write_text('created')"]) == 0
    record = json.loads(report.read_text().splitlines()[0]); assert record["status"] == "executed" and record["output_changed"] is True
    assert run_stage.main(["--report", str(report), "--name", "failure", "--kind", "validation", "--", sys.executable, "-c", "raise SystemExit(7)"]) == 7
    assert json.loads(report.read_text().splitlines()[-1])["status"] == "failed"


def test_finalize_reports_git_churn_and_network_costs(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"; root.mkdir(); subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE); subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True); subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    tracked = root / "tracked.txt"; tracked.write_text("before\n"); subprocess.run(["git", "add", "."], cwd=root, check=True); subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, stdout=subprocess.PIPE); tracked.write_text("after\n")
    monkeypatch.chdir(root); monkeypatch.setenv("UPDATE_RUN_STARTED_AT", "2026-09-22T00:00:00Z")
    records = [{"stage":"one","kind":"network","status":"executed","duration_seconds":1.25,"started_at":"2026-09-22T00:00:00Z","measurements_after":{"health.json":{"reported_request_count":22,"reported_fetched_records":350}}}]
    summary = finalize_update_telemetry.summarize(records, root)
    assert summary["stages"]["kind_seconds"]["network"] == 1.25; assert summary["network"]["reported_request_count"] == 22; assert summary["git"]["changed_file_count"] == 1; assert summary["git"]["git_patch_bytes"] > 0
