from datetime import UTC, datetime

from scripts.yahoo_evidence_graph import (
    build_evidence_graph,
    corroboration_blocker,
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


def test_blocker_explains_missing_peer_evidence() -> None:
    item = row(
        "1",
        "VRChat交流会 #VRC夜会 9/27 開催します。",
        anchor=datetime(2026, 9, 24, 10, tzinfo=UTC),
    )
    graph = build_evidence_graph([item], anchor_for=anchor_for)
    assert corroboration_blocker(
        item,
        graph=graph,
        anchor=anchor_for(item),
        actual_now=datetime(2026, 9, 25, tzinfo=UTC),
    ) == "no_peer_evidence"


def test_blocker_explains_conflicting_clock_evidence() -> None:
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
    assert corroboration_blocker(
        rows[0],
        graph=graph,
        anchor=anchor_for(rows[0]),
        actual_now=datetime(2026, 9, 25, tzinfo=UTC),
    ) == "missing_or_conflicting_clock"

def test_group_id_can_corroborate_across_different_authors() -> None:
    group_id = "grp_12345678-abcd-1234-abcd-1234567890ab"
    rows = [
        {
            **row(
                "1234567890123456789",
                f"VRChat交流会 #VRC夜会 9/27 開催します。Group {group_id}",
                author="host-a",
                anchor=datetime(2026, 9, 24, 10, tzinfo=UTC),
            ),
            "linked_urls": [f"https://vrchat.com/home/group/{group_id}"],
        },
        {
            **row(
                "2234567890123456789",
                f"VRChat交流会 #VRC夜会 22時半 JOIN案内 Group {group_id}",
                author="host-b",
                anchor=datetime(2026, 9, 24, 12, tzinfo=UTC),
            ),
            "linked_urls": [f"https://vrchat.com/home/group/{group_id}"],
        },
    ]
    graph = build_evidence_graph(rows, anchor_for=anchor_for)

    result = resolve_corroborated_datetime(
        rows[0],
        graph=graph,
        anchor=anchor_for(rows[0]),
        actual_now=datetime(2026, 9, 25, tzinfo=UTC),
    )
    assert result is not None
    assert result.event_at.isoformat() == "2026-09-27T22:30:00+09:00"
    assert result.event_fingerprint == f"group:{group_id}|hashtag:vrc夜会"


def test_reply_context_can_corroborate_across_different_authors() -> None:
    root_id = "1234567890123456789"
    reply_id = "2234567890123456789"
    first = {
        **row(
            root_id,
            "VRChat交流会 9/27 開催します。",
            author="host-a",
            anchor=datetime(2026, 9, 24, 10, tzinfo=UTC),
        ),
        "conversation_id": root_id,
    }
    second = {
        **row(
            reply_id,
            "開始は午後10時。Group +でJOINできます。",
            author="staff-b",
            anchor=datetime(2026, 9, 24, 12, tzinfo=UTC),
        ),
        "conversation_id": root_id,
        "in_reply_to_status_id": root_id,
    }
    graph = build_evidence_graph([first, second], anchor_for=anchor_for)

    result = resolve_corroborated_datetime(
        first,
        graph=graph,
        anchor=anchor_for(first),
        actual_now=datetime(2026, 9, 25, tzinfo=UTC),
    )
    assert result is not None
    assert result.event_at.isoformat() == "2026-09-27T22:00:00+09:00"
    assert result.event_fingerprint in {f"status:{root_id}", f"thread:{root_id}"}


def test_bracketed_event_name_is_available_as_author_scoped_fingerprint() -> None:
    item = row(
        "1234567890123456789",
        "【VRC夜会】9/27 開催します。",
        author="host",
        anchor=datetime(2026, 9, 24, 10, tzinfo=UTC),
    )
    assert "host|name:vrc夜会" in event_fingerprints(item)
