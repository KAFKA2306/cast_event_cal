from scripts import audit_partial_ambiguous_replay as replay


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
