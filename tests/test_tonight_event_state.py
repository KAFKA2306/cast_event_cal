from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


TONIGHT_JS = Path("public/tonight/tonight.js")


def _state_for(event: dict[str, str], now: str) -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute the public Tonight surface")

    source = TONIGHT_JS.read_text(encoding="utf-8")
    marker = "init()})();"
    assert marker in source
    instrumented = source.replace(
        marker,
        "globalThis.__tonightStateFor=stateFor})();",
        1,
    )
    script = (
        instrumented
        + "\nprocess.stdout.write(globalThis.__tonightStateFor("
        + json.dumps(event)
        + ",new Date("
        + json.dumps(now)
        + ")));"
    )
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_tonight_state_distinguishes_ended_from_same_day_candidates() -> None:
    now = "2026-09-14T12:00:00+09:00"

    assert _state_for({}, now) == "unknown"
    assert (
        _state_for(
            {
                "starts_at": "2026-09-14T09:00:00+09:00",
                "ends_at": "2026-09-14T10:00:00+09:00",
            },
            now,
        )
        == "ended"
    )
    assert (
        _state_for(
            {
                "starts_at": "2026-09-13T23:30:00+09:00",
                "ends_at": "2026-09-14T12:30:00+09:00",
            },
            now,
        )
        == "live"
    )
    assert _state_for({"starts_at": "2026-09-14T12:45:00+09:00"}, now) == "soon"
    assert _state_for({"starts_at": "2026-09-14T20:00:00+09:00"}, now) == "tonight"
    assert _state_for({"starts_at": "2026-09-15T20:00:00+09:00"}, now) == "future"
