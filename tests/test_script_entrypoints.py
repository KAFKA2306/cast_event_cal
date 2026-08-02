from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script_without_main(path: str) -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            f"import runpy; runpy.run_path({path!r}, run_name='entrypoint_import_test')",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_direct_daily_yahoo_entrypoint_imports():
    load_script_without_main("scripts/run_yahoo_realtime.py")


def test_direct_ledger_replay_entrypoint_imports():
    load_script_without_main("scripts/replay_yahoo_history.py")


def test_direct_frontend_renderer_entrypoint_imports():
    load_script_without_main("scripts/render_frontend.py")
