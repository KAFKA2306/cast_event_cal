from scripts.audit_yahoo_datetime_vocabulary import build, classify_missing_datetime, occurrence_decision


def row(status_id: str, text: str, reason: str = "missing_datetime") -> dict[str, object]:
    return {
        "status_id": status_id,
        "text": text,
        "last_decision": "rejected",
        "last_reason": reason,
    }


def test_datetime_failure_buckets_cover_supported_shapes() -> None:
    assert classify_missing_datetime("VRChat交流会 9 / 25 21:00 開催") == "explicit_datetime_unsupported"
    assert classify_missing_datetime("VRChat集会 今夜22:00 JOIN") == "relative_datetime_unsupported"
    assert classify_missing_datetime("VRChat集会 9/25 詳細後日") == "partial_datetime"
    assert classify_missing_datetime("VRChat集会 毎週金曜日 22:00") == "recurring_datetime"
    assert classify_missing_datetime("VRChatイベント開催決定 詳細後日") == "no_datetime_evidence"


def test_audit_is_exhaustive_and_deterministic() -> None:
    rows = [
        row("1", "VRChat交流会 9 / 25 21:00 開催"),
        row("2", "VRChat集会 今夜22:00 JOIN"),
        row("3", "VRChat集会 9/25 詳細後日"),
        row("4", "VRChat集会 毎週金曜日 22:00"),
        row("5", "VRChatイベント開催決定 詳細後日"),
        {
            "status_id": "6",
            "text": "VRChat交流会 9/25 22:00",
            "last_decision": "accepted",
            "last_reason": None,
        },
    ]

    first = build(rows)
    second = build(rows)

    assert first == second
    assert first["candidate_count"] == 6
    assert first["missing_datetime_count"] == 5
    assert first["missing_datetime_classified_count"] == 5
    assert first["missing_datetime_unclassified_count"] == 0
    assert first["temporal_evidence_count"] == 4
    assert first["bucket_counts"] == {
        "explicit_datetime_unsupported": 1,
        "no_datetime_evidence": 1,
        "partial_datetime": 1,
        "recurring_datetime": 1,
        "relative_datetime_unsupported": 1,
    }


def test_occurrence_decision_tree_is_explicit() -> None:
    assert occurrence_decision("VRChat交流会 9/25 21:00 開催します JOIN") == "resolvable_event_candidate"
    assert occurrence_decision("昨日のVRChatイベントに参加してきました 21:00 楽しかった") == "past_event_or_report"
    assert occurrence_decision("今日22:00に仕事から帰宅してVRCに入る") == "non_event_personal"
    assert occurrence_decision("BOOTH セール 本日22:00まで") == "non_event_commerce"
    assert occurrence_decision("VRChat集会 毎週金曜日 22:00 開催") == "recurring_event"
    assert occurrence_decision("VRChat集会 9/25 開催") == "partial_datetime"
    assert occurrence_decision("VRChat集会 今日22:00") == "ambiguous_datetime"


def test_temporal_candidates_all_receive_occurrence_decision() -> None:
    rows = [
        row("1", "VRChat交流会 9/25 21:00 開催します"),
        row("2", "昨日のVRChatイベントに参加してきました 21:00"),
        row("3", "今日22:00に仕事から帰宅してVRCに入る"),
        row("4", "BOOTH セール 本日22:00まで"),
        row("5", "VRChat集会 毎週金曜日 22:00 開催"),
        row("6", "VRChat集会 9/25 開催"),
        row("7", "VRChat集会 今日22:00"),
    ]
    audit = build(rows)
    assert audit["temporal_evidence_count"] == 7
    assert audit["occurrence_decision_total"] == 7
    assert audit["temporal_unclassified_count"] == 0
    assert sum(audit["occurrence_decision_counts"].values()) == 7
    assert audit["publishability_state_counts"] == {
        "confirmed_non_event": 2,
        "past_only": 1,
        "publishable_candidate": 1,
        "recurring_series_candidate": 1,
        "unresolved_publishability": 2,
    }
    assert audit["publishability_backlog_count"] == 3
    assert audit["automatic_resolution_candidate_count"] == 2
