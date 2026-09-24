from datetime import UTC, datetime

from scripts.yahoo_evidence_graph import (
    build_evidence_graph,
    event_fingerprints,
    resolve_corroborated_datetime,
)


def row(
    status_id: str,
    text: str,
    *,
    author: str = "host",
    anchor: datetime,
) -> dict[str, object]:
    return {
        "status_id": status_id,
        "text": text,
        "author": author,
        "_anchor": anchor,
    }


def anchor_for(item: dict[str, object]) -> datetime:
    return item["_anchor"]  # type: ignore[return-value]


def test_date_only_and_clock_only_same_event_fingerprint_resolve() -> None:
    first = row(
        "1",
        "VRChat交流会 #VRC夜会 9/27 開催します。Group +で参加できます。",
        anchor=datetime(2026, 9, 24, 10, tzinfo=UTC),
    )
    second = row(
        "2",
        "VRChat交流会 #VRC夜会 22:00 Group +でJOINできます。",
        anchor=datetime(2026, 9, 24, 12, tzinfo=UTC),
    )
    rows = [first, second]
    graph = build_evidence_graph(rows, anchor_for=anchor_for)

    result = resolve_corroborated_datetime(
        first,
        graph=graph,
        anchor=anchor_for(first),
        actual_now=datetime(2026, 9, 25, tzinfo=UTC),
    )

    assert result is not None
    assert result.event_at.isoformat() == "2026-09-27T22:00:00+09:00"
    assert result.method == "corroborated_event_fingerprint_date_clock"
    assert result.corroborating_source_ids == ("1", "2")
    assert "hashtag:vrc夜会" in result.event_fingerprint


def test_conflicting_clocks_fail_closed() -> None:
    rows = [
        row(
            "1",
            "VRChat交流会 #VRC夜会 9/27 開催します。",
            anchor=datetime(2026, 9, 24, 10, tzinfo=UTC),
        ),
        row(
            "2",
            "VRChat交流会 #VRC夜会 21:00 Group +でJOIN。",
            anchor=datetime(2026, 9, 24, 11, tzinfo=UTC),
        ),
        row(
            "3",
            "VRChat交流会 #VRC夜会 22:00 Group +でJOIN。",
            anchor=datetime(2026, 9, 24, 12, tzinfo=UTC),
        ),
    ]
    graph = build_evidence_graph(rows, anchor_for=anchor_for)

    assert resolve_corroborated_datetime(
        rows[0],
        graph=graph,
        anchor=anchor_for(rows[0]),
        actual_now=datetime(2026, 9, 25, tzinfo=UTC),
    ) is None


def test_different_authors_do_not_cross_fill() -> None:
    rows = [
        row(
            "1",
            "VRChat交流会 #VRC夜会 9/27 開催します。",
            author="host-a",
            anchor=datetime(2026, 9, 24, 10, tzinfo=UTC),
        ),
        row(
            "2",
            "VRChat交流会 #VRC夜会 22:00 Group +でJOIN。",
            author="host-b",
            anchor=datetime(2026, 9, 24, 11, tzinfo=UTC),
        ),
    ]
    graph = build_evidence_graph(rows, anchor_for=anchor_for)

    assert resolve_corroborated_datetime(
        rows[0],
        graph=graph,
        anchor=anchor_for(rows[0]),
        actual_now=datetime(2026, 9, 25, tzinfo=UTC),
    ) is None


def test_generic_vrchat_hashtag_is_not_an_event_fingerprint() -> None:
    item = row(
        "1",
        "VRChatイベント #VRChat 9/27 開催します。",
        anchor=datetime(2026, 9, 24, 10, tzinfo=UTC),
    )
    assert event_fingerprints(item) == set()
