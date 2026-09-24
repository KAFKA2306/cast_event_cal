from scripts.build_tonight_projection import FIELDS, build


def test_projection_preserves_identity_actions_and_filter_fields_without_extra_payload() -> None:
    canonical = {
        "generated_at": "2026-09-24T00:00:00Z",
        "events": [{
            "id": "evt-1",
            "title": "Test Event",
            "starts_at": "2026-09-24T12:00:00Z",
            "ends_at": "2026-09-24T13:00:00Z",
            "category": "music",
            "source": "official",
            "primary_action_url": "https://example.com/join",
            "official_links": [{"url": "https://example.com/event"}],
            "description": "visible summary",
            "provenance": {"large": "not needed by Tonight"},
            "ontology_evidence": ["not", "needed"],
        }],
    }

    result = build(canonical)

    assert result["generated_at"] == canonical["generated_at"]
    assert len(result["events"]) == len(canonical["events"])
    projected = result["events"][0]
    assert projected["id"] == "evt-1"
    assert projected["starts_at"] == canonical["events"][0]["starts_at"]
    assert projected["primary_action_url"] == canonical["events"][0]["primary_action_url"]
    assert projected["category"] == "music"
    assert projected["source"] == "official"
    assert "provenance" not in projected
    assert "ontology_evidence" not in projected
    assert set(projected) <= set(FIELDS)


def test_projection_is_deterministic_and_does_not_drop_events() -> None:
    payload = {"events": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]}
    assert build(payload) == build(payload)
    assert [event["id"] for event in build(payload)["events"]] == ["a", "b"]
