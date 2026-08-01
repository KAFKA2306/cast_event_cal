from datetime import UTC, datetime
import json
from pathlib import Path

from scripts.materialize_events import materialize, read_array


ROOT = Path(__file__).resolve().parents[1]


def test_materializes_rolling_120_day_window():
    events = materialize(
        read_array(ROOT / "data/recurring_events.json"),
        read_array(ROOT / "data/one_off_events.json"),
        now=datetime(2026, 8, 1, 21, 52, tzinfo=UTC),
        past_days=1,
        future_days=120,
    )
    assert len(events) == 70
    assert len({event["source_id"] for event in events}) == 70
    assert events[0]["starts_at"] == "2026-08-05T12:00:00Z"
    assert events[-1]["starts_at"] == "2026-11-27T13:00:00Z"
    titles = {event["title"] for event in events}
    assert {
        "水曜Quest初心者の集い",
        "ゆるゲMEET定期開催日",
        "VRC初心者ワールドツアー",
        "VRCふれあい動物園",
        "Pyropaw Pyrocon Showcase",
        "VRTon 2026",
    } <= titles


def test_generated_json_roundtrip(tmp_path):
    events = materialize(
        read_array(ROOT / "data/recurring_events.json"),
        read_array(ROOT / "data/one_off_events.json"),
        now=datetime(2026, 8, 1, 21, 52, tzinfo=UTC),
        past_days=1,
        future_days=120,
    )
    output = tmp_path / "events.json"
    output.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded == events
