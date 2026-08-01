from __future__ import annotations

import json
from pathlib import Path

from scripts.fetch_vrchat_calendar import normalize_event, run_discovery


def sample_event(**overrides):
    event = {
        "id": "cal_6b182f0c-61ef-4bdf-97fe-94f63bcba27b",
        "ownerId": "grp_71a7ff59-112c-4e78-a990-c7cc650776e5",
        "title": "日本語ゲーム交流会",
        "description": "初心者歓迎",
        "startsAt": "2026-08-10T12:00:00Z",
        "endsAt": "2026-08-10T13:00:00Z",
        "accessType": "public",
        "category": "gaming",
        "languages": ["jpn"],
        "platforms": ["standalonewindows", "android"],
        "tags": ["beginner"],
        "isDraft": False,
        "deletedAt": None,
    }
    event.update(overrides)
    return event


def test_normalize_event_accepts_public_calendar_event():
    event = normalize_event(sample_event())
    assert event is not None
    assert event["source_id"].startswith("cal_")
    assert event["starts_at"] == "2026-08-10T12:00:00Z"
    assert event["url"].endswith("/calendar/cal_6b182f0c-61ef-4bdf-97fe-94f63bcba27b")
    assert {"VRChat", "公式カレンダー", "jpn", "android"} <= set(event["tags"])


def test_normalize_event_rejects_non_public_or_deleted_event():
    assert normalize_event(sample_event(accessType="group")) is None
    assert normalize_event(sample_event(deletedAt="2026-08-01T00:00:00Z")) is None
    assert normalize_event(sample_event(isDraft=True)) is None


def test_missing_cookie_preserves_existing_cache(tmp_path: Path):
    output = tmp_path / "discovered.json"
    health = tmp_path / "health.json"
    exclude = tmp_path / "manual.json"
    cached = [{"source_id": "cal_cached", "title": "cached", "starts_at": "2026-08-10T12:00:00Z"}]
    output.write_text(json.dumps(cached), encoding="utf-8")
    exclude.write_text("[]", encoding="utf-8")

    result = run_discovery(
        cookie=None,
        output=output,
        health_output=health,
        exclude=exclude,
        terms=["日本語"],
        page_size=100,
        max_pages=1,
        timeout=1.0,
    )

    assert result == 0
    assert json.loads(output.read_text(encoding="utf-8")) == cached
    health_data = json.loads(health.read_text(encoding="utf-8"))
    assert health_data["status"] == "skipped"
    assert health_data["event_count"] == 1
