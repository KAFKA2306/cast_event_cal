from __future__ import annotations

import json
from pathlib import Path

import pytest

from cast_event_cal import mcp_read_model

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_PROVENANCE_KEYS = {
    "canonical_id",
    "schema_version",
    "event_start",
    "source_created_at",
    "first_seen_at",
    "last_seen_at",
    "generated_at",
    "source_type",
    "source_id",
    "source_url",
    "classification_rule",
    "classification_reason",
    "ontology_id",
    "freshness_seconds",
    "null_reasons",
}


def test_issue_47_event_provenance_contract_is_complete() -> None:
    payload = json.loads((ROOT / "public" / "events.json").read_text(encoding="utf-8"))
    first = payload["events"][0]
    item = mcp_read_model.get_event(first["id"])

    assert item is not None
    provenance = item["provenance"]
    assert REQUIRED_PROVENANCE_KEYS <= provenance.keys()
    assert provenance["canonical_id"] == first["id"]
    assert provenance["generated_at"] == payload["generated_at"]
    assert provenance["source_type"] == first.get("source")
    assert provenance["source_id"] == first.get("source_id")
    assert provenance["classification_reason"] == (first.get("category_evidence") or [])

    for key in ("source_created_at", "first_seen_at", "last_seen_at", "ontology_id"):
        if provenance[key] is None:
            assert provenance["null_reasons"][key] == "not_recorded_in_public_event"


def test_issue_47_search_pagination_is_fail_closed() -> None:
    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        mcp_read_model.search_events(limit=101)
    with pytest.raises(ValueError, match="offset must be non-negative"):
        mcp_read_model.search_events(offset=-1)


def test_issue_47_documented_tool_catalog_matches_contract() -> None:
    doc = (ROOT / "docs" / "event-mcp.md").read_text(encoding="utf-8")
    expected = {
        "search_events",
        "get_event",
        "get_tonight_events",
        "get_series",
        "get_source_health",
        "get_classification_audit",
        "get_ontology",
        "get_data_quality",
        "get_methodology",
    }
    assert all(f"`{name}`" in doc for name in expected)
    assert "KAFKA2306/vrc_cast_event_calender" in doc
    assert "classification logic is not canonical in the deployment repository" in doc.lower()
