from scripts import audit_yahoo_datetime_vocabulary as audit


def test_current_ledger_keeps_issue_196_semantic_north_star():
    report = audit.build(audit.read_candidates(audit.DEFAULT_INPUT))

    assert report["missing_datetime_unclassified_count"] == 0
    assert report["temporal_unclassified_count"] == 0
    assert report["occurrence_decision_total"] >= report["north_star_min_resolved_count"]
