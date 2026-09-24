from scripts.audit_yahoo_datetime_vocabulary import build, classify_missing_datetime


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
