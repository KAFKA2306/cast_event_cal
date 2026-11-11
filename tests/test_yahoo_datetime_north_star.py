from scripts import audit_yahoo_datetime_vocabulary as audit


def test_current_ledger_classifies_all_missing_datetime_evidence():
    report = audit.build(audit.read_candidates(audit.DEFAULT_INPUT))

    assert report["missing_datetime_unclassified_count"] == 0
    assert report["temporal_unclassified_count"] == 0

