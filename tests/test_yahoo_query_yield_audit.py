from scripts.audit_yahoo_query_yield import build_query_yield_audit


def test_query_yield_separates_unique_value_from_duplicate_noise() -> None:
    candidates = [
        {"status_id": "1", "query_keys": ["q-good"], "last_decision": "accepted"},
        {"status_id": "2", "query_keys": ["q-good", "q-dup"], "last_decision": "accepted"},
        {"status_id": "3", "query_keys": ["q-noise"], "last_decision": "rejected", "last_reason": "missing_datetime"},
    ] + [
        {"status_id": str(i), "query_keys": ["q-noise"], "last_decision": "rejected", "last_reason": "missing_datetime"}
        for i in range(4, 14)
    ]
    query_results = [
        {"key": "q-good", "group": "event", "term": "good", "status": "ok", "raw_candidates": 2, "html_bytes": 1_000_000, "duration_ms": 10},
        {"key": "q-dup", "group": "event", "term": "dup", "status": "ok", "raw_candidates": 1, "html_bytes": 500_000, "duration_ms": 8},
        {"key": "q-noise", "group": "event", "term": "noise", "status": "ok", "raw_candidates": 11, "html_bytes": 2_000_000, "duration_ms": 12},
    ]

    audit = build_query_yield_audit(candidates, query_results)
    rows = {row["query_key"]: row for row in audit["queries"]}

    assert rows["q-good"]["classification"] == "productive"
    assert rows["q-good"]["unique_only_accepted"] == 1
    assert rows["q-good"]["duplicate_discovery_candidates"] == 1
    assert rows["q-dup"]["classification"] == "redundant"
    assert rows["q-noise"]["classification"] == "high-noise"
    assert rows["q-noise"]["missing_datetime_rejections"] == 11
    assert audit["policy"]["auto_disable_queries"] is False
    assert audit["policy"]["coverage_evidence_required_before_removal"] is True


def test_missing_network_measurements_remain_unknown() -> None:
    audit = build_query_yield_audit(
        [{"status_id": "1", "query_keys": ["q"], "last_decision": "rejected", "last_reason": "other"}],
        [],
    )
    row = audit["queries"][0]
    assert row["response_bytes"] is None
    assert row["duration_ms"] is None
    assert row["accepted_per_mb"] is None
    assert row["coverage_evidence"] == "unavailable"
