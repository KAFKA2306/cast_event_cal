from scripts.audit_dedup_clusters import audit


def row(event_id: str, description: str, *, ordinal: int | None = None) -> dict:
    text = description if ordinal is None else f"第{ordinal}回 {description}"
    return {
        "id": event_id,
        "source": "yahoo_realtime_events",
        "source_id": event_id,
        "starts_at": "2026-10-01T13:00:00Z",
        "organizer": "@host",
        "description": text,
        "title": text,
        "url": f"https://x.com/host/status/{event_id}",
    }


def test_transitive_bridge_between_conflicting_ordinals_fails_closed() -> None:
    # A and C explicitly identify different occurrences. B omits the ordinal,
    # but is text-similar enough to both to create an unsafe A-B-C bridge.
    common = "VRChat交流イベントを22時から開催します 参加方法はGroup Joinです 詳細は公式告知を確認してください"
    events = [row("a", common, ordinal=4), row("b", common), row("c", common, ordinal=5)]

    report = audit(events)

    assert report["status"] == "unsafe"
    assert report["unsafe_cluster_count"] == 1
    assert report["unsafe_clusters"][0]["ordinals"] == ["4", "5"]


def test_single_occurrence_cluster_remains_safe() -> None:
    common = "VRChat交流イベントを22時から開催します 参加方法はGroup Joinです 詳細は公式告知を確認してください"
    events = [row("a", common, ordinal=4), row("b", common, ordinal=4)]

    report = audit(events)

    assert report["status"] == "ok"
    assert report["unsafe_cluster_count"] == 0
