import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "stage_metrics.py"


def run_metric(tmp_path: Path, *command: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    report = tmp_path / "metrics.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--report", str(report), "--name", "fixture", "--class", "validation", "--", *command],
        text=True,
        capture_output=True,
        check=False,
    )
    return result, json.loads(report.read_text(encoding="utf-8"))


def test_success_records_explicit_missing_measurements(tmp_path: Path) -> None:
    result, report = run_metric(tmp_path, sys.executable, "-c", "print('ok')")
    stage = report["stages"][0]
    assert result.returncode == 0
    assert stage["state"] == "executed"
    assert stage["exit_code"] == 0
    assert stage["duration_seconds"] >= 0
    assert stage["input_fingerprint"] is None
    assert stage["output_fingerprint"] is None
    assert stage["changed_bytes"] is None


def test_failure_is_recorded_and_exit_code_is_preserved(tmp_path: Path) -> None:
    result, report = run_metric(tmp_path, sys.executable, "-c", "raise SystemExit(7)")
    stage = report["stages"][0]
    assert result.returncode == 7
    assert stage["state"] == "failed"
    assert stage["exit_code"] == 7


def test_fingerprints_are_deterministic_for_declared_inputs(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    source.write_text("canonical\n", encoding="utf-8")
    report = tmp_path / "metrics.json"
    command = [
        sys.executable,
        str(SCRIPT),
        "--report",
        str(report),
        "--name",
        "projection",
        "--class",
        "projection",
        "--input",
        str(source),
        "--output",
        str(source),
        "--",
        sys.executable,
        "-c",
        "pass",
    ]
    subprocess.run(command, check=True)
    subprocess.run(command, check=True)
    stages = json.loads(report.read_text(encoding="utf-8"))["stages"]
    assert stages[0]["input_fingerprint"] == stages[1]["input_fingerprint"]
    assert stages[0]["output_fingerprint"] == stages[1]["output_fingerprint"]
