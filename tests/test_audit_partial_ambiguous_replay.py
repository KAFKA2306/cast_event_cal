from scripts import audit_partial_ambiguous_replay as replay


def test_partial_ambiguous_replay_reports_evidence_coverage() -> None:
    report = replay.audit()

    replay.assert_safety(report)
    assert report["schema_version"] == "1.2"
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
