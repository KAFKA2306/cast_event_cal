from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from cast_event_cal import mcp_read_model, mcp_server

ROOT = Path(__file__).resolve().parents[1]
JST = ZoneInfo("Asia/Tokyo")


def events_payload() -> dict:
    return json.loads((ROOT / "public" / "events.json").read_text(encoding="utf-8"))


def test_mcp_tool_catalog_is_discoverable() -> None:
    tools = asyncio.run(mcp_server.mcp.list_tools())
    assert {tool.name for tool in tools} == {
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


def test_public_events_and_mcp_search_are_same_records() -> None:
    payload = events_payload()
    first = payload["events"][0]
    page = mcp_read_model.search_events(limit=1)
    assert page["total"] == payload["count"] == len(payload["events"])
    projected = dict(page["items"][0])
    read_context = projected.pop("read_model_provenance")
    assert projected == first
    assert projected.get("provenance") == first.get("provenance")
    assert read_context["canonical_id"] == first["id"]
    assert read_context["schema_version"] == payload["schema_version"]
    assert read_context["event_start"] == first.get("starts_at")
    assert read_context["source_id"] == first.get("source_id")
    assert read_context["source_url"] == first.get("url")
    assert read_context["classification_rule"] == first.get("category_source")
    assert read_context["classification_reason"] == (first.get("category_evidence") or [])


def test_get_event_preserves_canonical_record() -> None:
    payload = events_payload()
    first = payload["events"][0]
    item = mcp_read_model.get_event(first["id"])
    assert item is not None
    projected = dict(item)
    projected.pop("read_model_provenance")
    assert projected == first
    assert projected.get("provenance") == first.get("provenance")


def test_tonight_replay_uses_explicit_jst_calendar_date() -> None:
    payload = events_payload()
    first_with_time = next(row for row in payload["events"] if row.get("starts_at"))
    starts = datetime.fromisoformat(first_with_time["starts_at"].replace("Z", "+00:00"))
    target = starts.astimezone(JST).date().isoformat()
    result = mcp_read_model.tonight_events(date_jst=target, limit=100)
    assert result["date_jst"] == target
    assert all(
        datetime.fromisoformat(item["starts_at"].replace("Z", "+00:00"))
        .astimezone(JST)
        .date()
        .isoformat()
        == target
        for item in result["items"]
    )


def test_series_is_human_curated_and_round_trips() -> None:
    ontology = mcp_read_model.ontology()
    first = ontology["entries"][0]
    assert mcp_read_model.get_series(first["canonical_id"]) == first
    assert ontology["governance"]["curation_mode"] == "human_only"
    assert ontology["matching_policy"]["ambiguous_match_action"] == "reject"


def test_data_quality_fails_closed_on_duplicates_and_ambiguity() -> None:
    quality = mcp_read_model.data_quality()
    assert quality["event_count_matches_health"] is True
    assert quality["duplicate_event_ids"] == 0
    assert quality["ontology_ambiguous_events"] == 0
    assert quality["ambiguous_match_action"] == "reject"
    assert quality["edinetdb_mode"] == "not_applicable"
    assert quality["canonical_repository"] == "KAFKA2306/cast_event_cal"
    assert all(len(item["sha256"]) == 64 for item in quality["artifacts"].values())


def test_methodology_keeps_deploy_repo_projection_only() -> None:
    methodology = mcp_read_model.methodology()
    assert methodology["canonical_repository"] == "KAFKA2306/cast_event_cal"
    assert methodology["deploy_repository"] == "KAFKA2306/vrc_cast_event_calender"
    assert methodology["llm_as_canonical_classifier"] is False
    assert methodology["classification"] == "deterministic_fail_close"
    assert methodology["time_semantics"]["timezone_for_tonight"] == "Asia/Tokyo"
