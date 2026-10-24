from scripts.audit_dedup_clusters import audit
from scripts.deduplicate_occurrences import occurrence_match


def row(event_id: str, description: str, *, source_id: str | None = None,
        url: str | None = None, title: str | None = None) -> dict:
    return {
        "id": event_id,
        "source": "yahoo_realtime_events",
        "source_id": source_id or event_id,
        "starts_at": "2026-10-01T13:00:00Z",
        "organizer": "@host",
        "description": description,
        "title": title or description,
        "url": url or f"https://x.com/host/status/{event_id}",
    }


def test_transitive_bridge_between_conflicting_ordinals_fails_closed() -> None:
    common = "VRChat交流イベントを22時から開催します 参加方法はGroup Joinです"
    a = row("a", "第4回 " + common, source_id="shared", title="fourth")
    b = row("b", common, source_id="shared",
            url="https://x.com/host/status/bridge", title="bridge")
    c = row("c", "第5回 " + common, source_id="unique",
            url="https://x.com/host/status/bridge", title="bridge")

    assert occurrence_match(a, b) is not None
    assert occurrence_match(b, c) is not None
    assert occurrence_match(a, c) is None

    report = audit([a, b, c])
    assert report["status"] == "unsafe"
    assert report["unsafe_cluster_count"] == 1
    assert report["unsafe_clusters"][0]["ordinals"] == ["4", "5"]


def test_same_ordinal_cluster_remains_safe() -> None:
    common = "VRChat交流イベントを22時から開催します 参加方法はGroup Joinです"
    url = "https://x.com/host/status/shared"
    a = row("a", "第4回 " + common, url=url, title="same")
    b = row("b", "第4回 " + common, url=url, title="same")
    assert occurrence_match(a, b) is not None
    report = audit([a, b])
    assert report["status"] == "ok"
    assert report["unsafe_cluster_count"] == 0
