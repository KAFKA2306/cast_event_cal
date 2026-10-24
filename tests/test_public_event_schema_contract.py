from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "audit_public_event_schema.py"
spec = importlib.util.spec_from_file_location("public_schema", MODULE_PATH)
assert spec and spec.loader
public_schema = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public_schema)


def event(**overrides):
    row = {"id": "evt-1", "title": "Example", "starts_at": "2026-10-01T19:00:00+09:00", "organizer": None}
    row.update(overrides)
    return row


def test_optional_addition_is_compatible_and_inventory_is_order_stable():
    left = public_schema.inventory([event(extra="x")])
    right = public_schema.inventory([dict(reversed(list(event(extra="x").items())))])
    assert public_schema.verify(left) == []
    assert left["fields"] == right["fields"]
    assert left["snapshotIdentity"] == right["snapshotIdentity"]
    assert left["fields"]["organizer"]["nullable"] is True


def test_required_field_removal_reports_affected_consumers():
    row = event()
    del row["starts_at"]
    failures = public_schema.verify(public_schema.inventory([row]))
    assert failures == [{
        "field": "starts_at",
        "reason": "required_field_missing",
        "affectedConsumers": ["atom", "calendar", "detail", "tonight"],
    }]


def test_required_field_type_drift_is_breaking():
    failures = public_schema.verify(public_schema.inventory([event(id={"legacy": "evt-1"})]))
    assert failures[0]["field"] == "id"
    assert failures[0]["reason"] == "required_field_type_drift"
    assert "identity" in failures[0]["affectedConsumers"]


def test_missing_required_value_is_not_defaulted():
    failures = public_schema.verify(public_schema.inventory([event(), {"id": "evt-2", "title": "No time"}]))
    assert any(item["reason"] == "required_field_missing_on_records" and item["count"] == 1 for item in failures)
