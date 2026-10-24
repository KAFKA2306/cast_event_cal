"""Behavioral regression for deterministic Tonight ordering and page boundaries."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

TONIGHT_JS = Path(__file__).resolve().parents[1] / "public" / "tonight" / "tonight.js"


def sorted_ids(events):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute the Tonight comparator")
    source = TONIGHT_JS.read_text(encoding="utf-8")
    marker = "init()})();"
    assert source.endswith(marker)
    instrumented = source[: -len(marker)] + "globalThis.__compareEvents=compareEvents})();"
    script = (
        instrumented
        + "\nconst events = "
        + json.dumps(events)
        + ";\nprocess.stdout.write(JSON.stringify(events.sort(globalThis.__compareEvents).map(e => e.id)));"
    )
    result = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def test_chronological_and_unknown_time_order_independent_of_input():
    rows = [
        {"id": "later", "starts_at": "2026-10-24T12:00:00Z"},
        {"id": "unknown-b"},
        {"id": "same-10", "starts_at": "2026-10-24T11:00:00Z"},
        {"id": "earlier", "starts_at": "2026-10-24T10:00:00Z"},
        {"id": "unknown-a", "starts_at": "invalid"},
        {"id": "same-2", "starts_at": "2026-10-24T11:00:00Z"},
    ]
    expected = ["earlier", "same-2", "same-10", "later", "unknown-a", "unknown-b"]
    assert sorted_ids(rows) == expected
    assert sorted_ids(list(reversed(rows))) == expected


def test_equal_time_first_page_is_stable_after_shuffle():
    rows = [
        {"id": f"event-{i:02d}", "starts_at": "2026-10-24T11:00:00Z"}
        for i in range(35)
    ]
    expected_first_page = [f"event-{i:02d}" for i in range(30)]
    assert sorted_ids(rows)[:30] == expected_first_page
    assert sorted_ids(list(reversed(rows)))[:30] == expected_first_page
