import json
from scripts.audit_coverage import audit

def gold():
    return {"items":[{"event_identity":"known-1","evidence_url":"https://example.org/e","starts_at":"2026-09-22T22:00:00+09:00","category":"world_tour","observed_at":"2026-09-22T09:00:00+09:00","expected_sources":["source-a"],"provenance":"fixture"}]}

def test_found_is_counted_by_category_and_source():
    r=audit(gold(),{"events":[{"event_identity":"known-1"}],"supported_sources":["source-a"]})
    assert r["items"][0]["status"]=="found"
    assert r["by_category"]["world_tour"]["recall"]==1.0
    assert r["by_source"]["source-a"]["recall"]==1.0

def test_source_outage_is_not_silently_counted_as_miss():
    r=audit(gold(),{"events":[],"supported_sources":["source-a"],"source_unavailable":["source-a"]})
    assert r["items"][0]["status"]=="source_unavailable"
    assert r["items"][0]["miss_reason"] is None
    assert r["by_source"]["source-a"]["recall"] is None

def test_not_found_keeps_machine_readable_pipeline_reason():
    r=audit(gold(),{"events":[],"supported_sources":["source-a"],"miss_reasons":{"known-1":"parser_miss"}})
    assert r["items"][0]=={"event_identity":"known-1","status":"not_found","miss_reason":"parser_miss","category":"world_tour","expected_sources":["source-a"]}

def test_unsupported_is_distinct_from_miss():
    r=audit(gold(),{"events":[],"supported_sources":["source-b"]})
    assert r["items"][0]["status"]=="unsupported"
    assert r["by_source"]["source-a"]["recall"] is None
