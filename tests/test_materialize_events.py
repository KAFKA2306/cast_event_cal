import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.materialize_events import materialize, parse_instant, read_array


ROOT = Path(__file__).resolve().parents[1]
JST = ZoneInfo("Asia/Tokyo")


def test_materializes_rolling_120_day_window():
    events = materialize(
        read_array(ROOT / "data/recurring_events.json"),
        read_array(ROOT / "data/one_off_events.json"),
        now=datetime(2026, 8, 1, 21, 52, tzinfo=UTC),
        past_days=1,
        future_days=120,
    )
    assert len(events) >= 250
    assert len({event["source_id"] for event in events}) == len(events)
    local_days = [parse_instant(event["starts_at"]).astimezone(JST).date() for event in events]
    assert min(local_days).isoformat() == "2026-08-01"
    assert max(local_days).isoformat() <= "2026-11-30"
    titles = {event["title"] for event in events}
    assert {
        "おはよう！朝4時に何してるんだぃ？",
        "EN-JP Language Exchange（土曜）",
        "VRCゲームワールド部",
        "VRCフィットボクシング（土曜）",
        "しーぷかふぇ（第2・第4土曜 前半）",
        "VR研究カフェ",
        "謎めぐり",
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
