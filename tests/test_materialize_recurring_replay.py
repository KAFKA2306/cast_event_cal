import json
from datetime import UTC, datetime

import pytest

from scripts.materialize_recurring_replay import materialize, sync_health

NOW = datetime(2026, 10, 2, tzinfo=UTC)


def candidate() -> dict:
    return {
        "status_id": "2100790611721048254",
        "url": "https://x.com/example/status/2100790611721048254",
        "text": "VRChat 定期イベント 毎週木曜日 22:00 開催 ご参加ください",
        "retweet_count": 5,
    }


def report(*, provenance_fail: int = 0) -> dict:
    return {
        "resolver_version": "recurrence-v1",
        "promotions_without_provenance": provenance_fail,
        "results": [
            {
                "status_id": "2100790611721048254",
                "url": "https://x.com/example/status/2100790611721048254",
                "resolved": True,
                "future_starts": ["2026-10-08T22:00:00+09:00"],
                "rule": {"frequency": "weekly", "weekdays": [3], "local_time": "22:00", "timezone": "Asia/Tokyo"},
            }
        ],
    }


def test_materializes_only_replay_proven_occurrence() -> None:
    def builder(candidate, *, event_at, now, min_retweets, x_ids):
        assert event_at.isoformat() == "2026-10-08T13:00:00+00:00"
        return {
            "source_id": f"yahoo:x:{candidate['status_id']}",
            "title": "定期イベント",
            "starts_at": "2026-10-08T13:00:00Z",
            "description": candidate["text"],
            "url": candidate["url"],
            "category": "event",
            "tags": ["VRChat"],
        }, None

    events, stats = materialize([candidate()], report(), [], now=NOW, min_retweets=3, x_ids=set(), builder=builder)
    assert stats["materialized"] == 1
    assert events[0]["recurrence_resolver_version"] == "recurrence-v1"
    assert events[0]["recurrence_provenance_url"].startswith("https://x.com/")
    assert "定期開催" in events[0]["tags"]


def test_sync_health_tracks_materialized_output_count(tmp_path) -> None:
    path = tmp_path / "health.json"
    path.write_text(json.dumps({"status": "ok", "materialized_event_count": 1}), encoding="utf-8")

    sync_health([{"source_id": "one"}, {"source_id": "two"}], path=path)

    health = json.loads(path.read_text(encoding="utf-8"))
    assert health["status"] == "ok"
    assert health["event_count"] == 2
    assert health["materialized_event_count"] == 2


def test_fails_closed_when_replay_gate_failed() -> None:
    with pytest.raises(ValueError, match="promotions without provenance"):
        materialize([candidate()], report(provenance_fail=1), [], now=NOW, min_retweets=3, x_ids=set())
