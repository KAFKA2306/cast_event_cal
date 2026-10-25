import pytest

from scripts.build_tonight_projection import FIELDS, build


def test_projection_preserves_tonight_fields_and_omits_heavy_internal_payload() -> None:
    canonical = {
        "generated_at": "2026-10-25T00:00:00Z",
        "events": [
            {
                "id": "evt-1",
                "title": "Test Event",
                "starts_at": "2026-10-25T12:00:00Z",
                "ends_at": "2026-10-25T13:00:00Z",
                "category": "music",
                "source": "official",
                "primary_action_url": "https://example.com/join",
                "official_links": [{"url": "https://example.com/event"}],
                "official_url": "https://example.com/official",
                "join_url": "https://example.com/join-now",
                "description": "visible summary",
                "proof_links": ["https://example.com/proof"],
                "provenance": {"large": "not needed by Tonight"},
                "ontology_evidence": ["not", "needed"],
            }
        ],
    }
    result = build(canonical)
    assert result["generated_at"] == canonical["generated_at"]
    assert len(result["events"]) == len(canonical["events"])
    projected = result["events"][0]
    for field in ("id", "starts_at", "primary_action_url", "category", "source", "official_url", "join_url", "proof_links"):
        assert projected[field] == canonical["events"][0][field]
    assert "provenance" not in projected
    assert "ontology_evidence" not in projected
    assert set(projected) <= set(FIELDS)


def test_legacy_tonight_aliases_are_not_lost() -> None:
    canonical = {
        "events": [
            {
                "event_id": "legacy-1",
                "event_name": "Legacy Event",
                "start_at": "2026-10-25T12:00:00Z",
                "end_at": "2026-10-25T13:00:00Z",
                "source_url": "https://example.com/source",
                "participation_url": "https://example.com/participate",
                "evidence_links": ["https://example.com/evidence"],
                "summary": "Legacy description",
            }
        ]
    }
    assert build(canonical)["events"][0] == canonical["events"][0]


def test_projection_deterministic_and_preserves_event_order() -> None:
    payload = {"events": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]}
    assert build(payload) == build(payload)
    assert [event["id"] for event in build(payload)["events"]] == ["a", "b"]


def test_malformed_canonical_event_fails_closed() -> None:
    with pytest.raises(ValueError, match="non-object"):
        build({"events": [{"id": "a"}, None]})
