import json
import os
import re
import subprocess
from pathlib import Path


SCRIPT = Path("public/tonight/tonight.js")


def _range_end(now: str, range_name: str) -> str:
    source = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"function rangeEnd\(\)\{.*?return end\}", source)
    assert match, "rangeEnd must remain independently executable"
    js = f"""
const RealDate = Date;
const fixed = new RealDate({json.dumps(now)});
global.Date = class extends RealDate {{
  constructor(value) {{ super(value === undefined ? fixed.getTime() : value); }}
}};
const state = {{range: {json.dumps(range_name)}}};
{match.group(0)}
console.log(rangeEnd().toISOString());
"""
    env = os.environ | {"TZ": "Asia/Tokyo"}
    result = subprocess.run(
        ["node", "-e", js], check=True, capture_output=True, text=True, env=env
    )
    return result.stdout.strip()


def test_today_includes_late_same_day_but_not_tomorrow():
    assert _range_end("2026-09-29T01:00:00+09:00", "today") == "2026-09-29T14:59:59.999Z"


def test_seven_day_range_ends_on_seventh_calendar_day():
    assert _range_end("2026-09-29T23:30:00+09:00", "week") == "2026-10-05T14:59:59.999Z"


def test_thirty_day_range_crosses_month_boundary_by_calendar_date():
    assert _range_end("2026-01-31T12:00:00+09:00", "month") == "2026-03-01T14:59:59.999Z"
