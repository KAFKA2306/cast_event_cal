from scripts.audit_coverage import audit


def gold():
    return {
        "items": [
            {
                "event_identity": "known-1",
                "evidence_url": "https://example.org/e",
                "starts_at": "2026-09-22T22:00:00+09:00",
                "category": "world_tour",
                "observed_at": "2026-09-22T09:00:00+09:00",
                "expected_sources": ["source-a"],
                "provenance": "fixture",
            }
        ]
    }


def test_found_is_counted_by_category_and_source():
    result = audit(
        gold(),
        {"events": [{"event_identity": "known-1"}], "supported_sources": ["source-a"]},
    )
    assert result["items"][0]["status"] == "found"
    assert result["by_category"]["world_tour"]["recall"] == 1.0
    assert result["by_source"]["source-a"]["recall"] == 1.0


def test_source_outage_is_not_silently_counted_as_miss():
    result = audit(
        gold(),
        {
            "events": [],
            "supported_sources": ["source-a"],
            "source_unavailable": ["source-a"],
        },
    )
    assert result["items"][0]["status"] == "source_unavailable"
    assert result["items"][0]["miss_reason"] is None
    assert result["by_source"]["source-a"]["recall"] is None


def test_not_found_keeps_machine_readable_pipeline_reason():
    result = audit(
        gold(),
        {
            "events": [],
            "supported_sources": ["source-a"],
            "miss_reasons": {"known-1": "parser_miss"},
        },
    )
    assert result["items"][0] == {
        "event_identity": "known-1",
        "status": "not_found",
        "miss_reason": "parser_miss",
        "category": "world_tour",
        "expected_sources": ["source-a"],
    }


def test_unsupported_is_distinct_from_miss():
    result = audit(gold(), {"events": [], "supported_sources": ["source-b"]})
    assert result["items"][0]["status"] == "unsupported"
    assert result["by_source"]["source-a"]["recall"] is None
