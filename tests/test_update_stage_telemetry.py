from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import finalize_update_telemetry, run_stage


def test_fingerprint_is_stable_and_ignores_runtime_cache(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"; source.write_text("alpha", encoding="utf-8")
    first = run_stage.fingerprint_paths(tmp_path, [str(source)])
    assert run_stage.fingerprint_paths(tmp_path, [str(source)]) == first
    source.write_text("beta", encoding="utf-8")
    assert run_stage.fingerprint_paths(tmp_path, [str(source)])["sha256"] != first["sha256"]


def test_projection_reuses_only_matching_input_and_code(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path); report = tmp_path / "telemetry.jsonl"; cache = tmp_path / "cache"
    source = tmp_path / "input.txt"; source.write_text("one", encoding="utf-8")
    code = tmp_path / "projection.py"; code.write_text("v1", encoding="utf-8")
    output = tmp_path / "output.txt"
    command = "from pathlib import Path; Path('output.txt').write_text(Path('input.txt').read_text())"
    args = ["--report", str(report), "--name", "fixture", "--kind", "projection", "--input", "input.txt", "--code-input", "projection.py", "--output", "output.txt", "--cache-root", str(cache), "--", sys.executable, "-c", command]
    assert run_stage.main(args) == 0
    output.unlink()
    assert run_stage.main(args) == 0
    assert output.read_text() == "one"
    records = [json.loads(line) for line in report.read_text().splitlines()]
    assert [row["status"] for row in records] == ["executed", "reused"]
    code.write_text("v2", encoding="utf-8"); output.unlink()
    assert run_stage.main(args) == 0
    assert json.loads(report.read_text().splitlines()[-1])["status"] == "executed"


def test_cache_reuse_is_rejected_for_network_stage(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        run_stage.parse_args(["--report", "x", "--name", "net", "--kind", "network", "--cache-root", str(tmp_path), "--", "true"])


def test_stage_propagates_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path); report = tmp_path / "telemetry.jsonl"
    args = ["--report", str(report), "--name", "failure", "--kind", "validation", "--", sys.executable, "-c", "raise SystemExit(7)"]
    assert run_stage.main(args) == 7
    assert json.loads(report.read_text().splitlines()[-1])["status"] == "failed"


def test_finalize_reports_git_churn_and_network_costs(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"; root.mkdir(); subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True); subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    tracked = root / "tracked.txt"; tracked.write_text("before\n"); subprocess.run(["git", "add", "."], cwd=root, check=True); subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, stdout=subprocess.PIPE); tracked.write_text("after\n")
    monkeypatch.chdir(root); monkeypatch.setenv("UPDATE_RUN_STARTED_AT", "2026-09-22T00:00:00Z")
    records = [{"stage": "one", "kind": "network", "status": "executed", "duration_seconds": 1.25, "started_at": "2026-09-22T00:00:00Z", "measurements_after": {"health.json": {"reported_request_count": 22, "reported_fetched_records": 350}}}]
    summary = finalize_update_telemetry.summarize(records, root)
    assert summary["stages"]["kind_seconds"]["network"] == 1.25
    assert summary["network"]["reported_request_count"] == 22
    assert summary["git"]["changed_file_count"] == 1
    assert summary["git"]["git_patch_bytes"] > 0
