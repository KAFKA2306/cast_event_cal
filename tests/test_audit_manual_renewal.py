from datetime import UTC, datetime

import pytest

from scripts.audit_manual_renewal import audit, classify

NOW = datetime(2026, 9, 27, 14, 0, tzinfo=UTC)


def test_audit_is_deterministic_and_limits_human_queue_to_due_states() -> None:
    records = [
        {"series_id": "fresh", "title": "Fresh", "url": "https://example.com/fresh", "last_verified_at": "2026-09-20T00:00:00Z", "provenance": {"source": "official"}},
        {"series_id": "due", "title": "Due", "url": "https://example.com/due", "last_verified_at": "2026-07-10T00:00:00Z"},
        {"series_id": "old", "title": "Old", "url": "https://example.com/old", "last_verified_at": "2026-01-01T00:00:00Z"},
        {"series_id": "unknown", "title": "Unknown"},
    ]
    first = audit(records, now=NOW, due_days=90)
    second = audit(list(reversed(records)), now=NOW, due_days=90)

    assert first == second
    assert first["state_counts"] == {"verified": 1, "due": 1, "overdue": 1, "unknown": 1}
    assert first["human_queue"] == ["due", "old", "unknown"]


def test_missing_evidence_is_never_promoted_to_fresh() -> None:
    result = classify({"source_id": "manual-1", "url": "https://example.com/event"}, now=NOW, due_days=90)
    assert result["verification_state"] == "unknown"
    assert result["last_verified_at"] is None
    assert result["machine_verifiable_official_url"] is True
    assert result["evidence_present"] is False


def test_url_reachability_is_not_treated_as_continuation_evidence() -> None:
    result = classify({"series_id": "series-1", "url": "https://example.com/event", "last_verified_at": "2025-01-01T00:00:00Z"}, now=NOW, due_days=90)
    assert result["machine_verifiable_official_url"] is True
    assert result["verification_state"] == "overdue"


def test_invalid_verification_time_fails_closed() -> None:
    result = classify({"series_id": "bad-time", "last_verified_at": "yesterday"}, now=NOW, due_days=90)
    assert result["verification_state"] == "unknown"
    assert result["reason"] == "invalid_last_verified_at"


def test_record_without_stable_identity_is_rejected() -> None:
    with pytest.raises(ValueError, match="stable identity"):
        classify({"title": "No identity"}, now=NOW, due_days=90)
