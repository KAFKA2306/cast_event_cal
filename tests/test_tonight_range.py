import json
import os
import re
import subprocess
from pathlib import Path


SCRIPT = Path("public/tonight/tonight.js")


def _range_window(now: str, range_name: str, tz: str) -> dict[str, str]:
    source = SCRIPT.read_text(encoding="utf-8")
    start_match = re.search(r"function jstDayStart\(.*?\}\n?function rangeWindow", source)
    if not start_match:
        start_match = re.search(r"function jstDayStart\(.*?\}\s*function rangeWindow", source)
    assert start_match, "JST range policy must remain independently executable"
    helpers = start_match.group(0).removesuffix("function rangeWindow")
    window_match = re.search(r"function rangeWindow\(.*?\}\}", source)
    assert window_match, "rangeWindow must remain independently executable"
    js = f"""
const RealDate = Date;
const fixed = new RealDate({json.dumps(now)});
global.Date = class extends RealDate {{
  constructor(value) {{ super(value === undefined ? fixed.getTime() : value); }}
}};
const state = {{range: {json.dumps(range_name)}}};
{helpers}
{window_match.group(0)}
const window = rangeWindow();
console.log(JSON.stringify({{start: window.start.toISOString(), end: window.end.toISOString()}}));
"""
    result = subprocess.run(
        ["node", "-e", js],
        check=True,
        capture_output=True,
        text=True,
        env=os.environ | {"TZ": tz},
    )
    return json.loads(result.stdout)


def test_today_is_jst_day_with_exclusive_end():
    expected = {
        "start": "2026-09-28T15:00:00.000Z",
        "end": "2026-09-29T15:00:00.000Z",
    }
    for tz in ("UTC", "Asia/Tokyo", "America/Los_Angeles"):
        assert _range_window("2026-09-29T01:00:00+09:00", "today", tz) == expected


def test_today_boundary_does_not_double_assign_next_day():
    window = _range_window("2026-09-29T23:59:59+09:00", "today", "UTC")
    end = window["end"]
    assert window["start"] == "2026-09-28T15:00:00.000Z"
    assert end == "2026-09-29T15:00:00.000Z"
    assert "2026-09-29T14:59:59.999Z" < end
    assert "2026-09-29T15:00:00.000Z" == end


def test_seven_thirty_and_120_day_windows_are_calendar_day_counts():
    expected_ends = {
        "week": "2026-10-05T15:00:00.000Z",
        "month": "2026-10-28T15:00:00.000Z",
        "all": "2027-01-26T15:00:00.000Z",
    }
    for range_name, expected_end in expected_ends.items():
        window = _range_window("2026-09-29T23:30:00+09:00", range_name, "America/New_York")
        assert window["start"] == "2026-09-28T15:00:00.000Z"
        assert window["end"] == expected_end


def test_month_boundary_is_timezone_independent():
    expected = {
        "start": "2026-01-30T15:00:00.000Z",
        "end": "2026-03-01T15:00:00.000Z",
    }
    for tz in ("UTC", "Asia/Tokyo", "America/Los_Angeles"):
        assert _range_window("2026-01-31T12:00:00+09:00", "month", tz) == expected


def test_filter_uses_exclusive_window_contract():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "start>=window.start&&start<window.end" in source
    assert "getFullYear()" not in source
    assert "getMonth()" not in source
    assert "getDate()" not in source
