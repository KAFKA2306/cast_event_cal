from __future__ import annotations

from pathlib import Path

from scripts.audit_analytics_contract import empty_projection, load_contract, validate_record

ROOT = Path(__file__).resolve().parents[1]


def contract():
    return load_contract(ROOT / "config" / "analytics_event_contract.json")


def test_actual_official_source_observation_is_valid() -> None:
    record = {
        "schema_version": "1.0",
        "event_type": "official_source_opened",
        "surface": "event_detail",
        "event_id": "evt_1",
        "destination_type": "official",
        "observed_at": "2026-09-23T00:00:00Z",
        "observation_kind": "actual",
        "referrer_state": "unverified",
    }
    assert validate_record(record, contract()) == []


def test_synthetic_and_actual_are_explicit_and_private_fields_fail() -> None:
    base = {
        "schema_version": "1.0",
        "event_type": "surface_opened",
        "surface": "tonight",
        "observed_at": "2026-09-23T00:00:00Z",
    }
    assert "invalid_observation_kind" in validate_record({**base, "observation_kind": "unknown"}, contract())
    errors = validate_record({**base, "observation_kind": "synthetic", "event_title": "secret-ish payload"}, contract())
    assert "forbidden:event_title" in errors


def test_empty_projection_is_not_observed_not_fake_zero_success() -> None:
    projection = empty_projection(contract())
    assert projection["status"] == "NOT_OBSERVED"
    assert all(value == 0 for value in projection["event_counts"].values())
