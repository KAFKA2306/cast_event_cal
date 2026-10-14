import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_semantic_collisions import audit


def _run(tmp_path, events):
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"events": events}), encoding="utf-8")
    return audit(path)


def test_cross_source_collision_and_order_independence(tmp_path):
    events = [
        {"id": "x-1", "title": "VRC Dance Night!", "start": "2026-10-01T21:00:00+09:00", "official_url": "https://example.com/event?utm_source=x"},
        {"id": "cal-9", "title": "ＶＲＣ Dance Night！", "start": "2026-10-01T21:00:00+09:00", "official_url": "https://example.com/event?ref=calendar"},
    ]
    forward = _run(tmp_path, events)
    reverse = _run(tmp_path, list(reversed(events)))
    assert forward == reverse
    assert forward["collision_count"] == 1
    assert forward["collisions"][0]["classification"] == "high_confidence"
    assert forward["collisions"][0]["member_ids"] == ["id:cal-9", "id:x-1"]
    assert forward["collisions"][0]["evidence_fields"] == ["title", "url"]


def test_same_time_different_event_is_insufficient(tmp_path):
    report = _run(tmp_path, [
        {"id": "a", "title": "Study Group", "start": "2026-10-01T21:00:00+09:00"},
        {"id": "b", "title": "Dance Party", "start": "2026-10-01T21:00:00+09:00"},
    ])
    assert report["collision_count"] == 0
    assert report["insufficient_evidence"][0]["classification"] == "insufficient_evidence"


def test_title_only_match_is_review_candidate(tmp_path):
    report = _run(tmp_path, [
        {"id": "a", "title": "Language Exchange", "start": "2026-10-01T21:00:00+09:00"},
        {"id": "b", "title": "Language Exchange", "start": "2026-10-01T21:00:00+09:00"},
    ])
    assert report["collisions"][0]["classification"] == "review_candidate"
    assert report["collisions"][0]["evidence_fields"] == ["title"]
