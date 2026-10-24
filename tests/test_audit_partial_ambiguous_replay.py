from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import audit_partial_ambiguous_replay as replay

JST = ZoneInfo("Asia/Tokyo")


def test_partial_ambiguous_replay_reports_evidence_coverage() -> None:
    report = replay.audit()

    replay.assert_safety(report)
    assert report["schema_version"] == "1.3"
    assert report["input_total"] > 0
    assert report["evidence_graph_matched"] >= report["evidence_graph_conflicted"]
    assert report["evidence_graph_matched"] + report["resolution_blocker_counts"].get(
        "no_peer_evidence", 0
    ) == report["input_total"]
    assert sum(report["date_blocker_detail_counts"].values()) == report[
        "resolution_blocker_counts"
    ].get("missing_or_conflicting_date", 0)
    assert all(
        "event_fingerprints" in sample
        for samples in report["blocker_samples"].values()
        for sample in samples
    )
    assert set(report["fingerprint_kind_counts_by_blocker"]) == set(report["resolution_blocker_counts"])
    assert all(
        sum(counts.values()) >= report["resolution_blocker_counts"][blocker]
        for blocker, counts in report["fingerprint_kind_counts_by_blocker"].items()
    )


def test_conflicting_date_audit_is_complete_and_bounded() -> None:
    report = replay.audit()
    conflicting = report["date_blocker_detail_counts"].get("conflicting_date", 0)

    assert sum(report["conflicting_date_semantic_counts"].values()) == conflicting
    assert set(report["conflicting_date_semantic_counts"]) <= {
        "event_occurrence",
        "application_or_recruitment_deadline",
        "event_period",
        "multiple_occurrences",
        "past_event_or_activity_report",
        "other_or_undetermined",
    }
    if conflicting:
        assert report["conflicting_date_fingerprint_family_counts"]
        assert report["top_conflicting_date_fingerprints"]
        assert all(
            sample["status_id"]
            for samples in report["conflicting_date_samples"].values()
            for sample in samples
        )


def test_conflicting_date_fingerprint_families_are_stable() -> None:
    assert replay.fingerprint_family("thread:1234567890") == "thread"
    assert replay.fingerprint_family("eventtitle:vrc夜会") == "event_title"
    assert replay.fingerprint_family("officialurl:https://example.com/event") == "url"
    assert replay.fingerprint_family("alice|groupcode:night.1234") == "vrchat_group"
    assert replay.fingerprint_family("alice|hashtag:vrc夜会") == "author_series"



def test_row_date_semantics_use_current_row_date_context() -> None:
    anchor = datetime(2026, 10, 4, 12, 0, tzinfo=JST)

    cases = [
        (
            "出演応募の締切は10/5 23:59です",
            "application_or_recruitment_deadline",
        ),
        (
            "10/11〜10/16の期間で開催します",
            "event_period",
        ),
        (
            "10/10と10/11の両日に開催します",
            "multiple_occurrences",
        ),
        (
            "7/4に開催した集会の集合写真です",
            "past_event_or_activity_report",
        ),
        (
            "本日開催。21:00 OPEN、22:00開始です",
            "event_occurrence",
        ),
        (
            "10/1発売予定です。商品詳細は後日公開します",
            "other_or_undetermined",
        ),
    ]

    for text, expected in cases:
        assert replay.classify_row_date_semantics(
            {"text": text},
            anchor=anchor,
        ) == expected



def test_unscoped_event_title_conflicts_are_not_treated_as_safe_fingerprints() -> None:
    anchor = datetime(2026, 10, 4, 12, 0, tzinfo=JST)
    fingerprint = "eventtitle:nightmeeting"
    row = {
        "status_id": "1111111111111111111",
        "text": "『NightMeeting』 10/10 開催",
    }
    graph = {
        fingerprint: [
            replay.evidence_graph.EvidenceNode(
                status_id="1111111111111111111",
                anchor=anchor,
                text="『NightMeeting』 10/10 開催",
            ),
            replay.evidence_graph.EvidenceNode(
                status_id="2222222222222222222",
                anchor=anchor,
                text="『NightMeeting』 10/11 開催",
            ),
        ]
    }

    _nodes, fingerprints = replay.conflicting_date_context(
        row,
        graph=graph,
        anchor=anchor,
    )
    assert fingerprint not in fingerprints

    graph[fingerprint].append(
        replay.evidence_graph.EvidenceNode(
            status_id="external:official",
            anchor=anchor,
            text="2026/10/10 21:00 開催",
        )
    )
    _nodes, fingerprints = replay.conflicting_date_context(
        row,
        graph=graph,
        anchor=anchor,
    )
    assert fingerprint in fingerprints


def test_unmarked_multiple_dates_remain_undetermined() -> None:
    anchor = datetime(2026, 10, 4, 12, 0, tzinfo=JST)
    row = {
        "text": "10/10開催予定でした。日程変更で10/11開催予定です",
    }

    assert replay.classify_row_date_semantics(
        row,
        anchor=anchor,
    ) == "other_or_undetermined"
