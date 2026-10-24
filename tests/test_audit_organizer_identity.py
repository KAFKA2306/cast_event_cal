from scripts.audit_organizer_identity import audit, normalize_label


def test_normalization_is_display_safe_and_deterministic():
    assert normalize_label("  Cafe\u3000KAFKA  ") == "cafe kafka"


def test_strong_identity_merges_whitespace_variants():
    events = [
        {"id": "b", "organizer": "Cafe KAFKA", "group_id": "grp_1", "series": "night"},
        {"id": "a", "organizer": " Cafe\u3000KAFKA ", "group_id": "GRP_1", "series": "night"},
    ]
    candidate = audit(events)["candidates"][0]
    assert candidate["decision"] == "merged"
    assert candidate["event_ids"] == ["a", "b"]
    assert candidate["evidence"] == ["vrchat-group:grp_1"]


def test_same_display_name_with_conflicting_strong_evidence_stays_distinct():
    events = [
        {"id": "a", "organizer": "Same Name", "group_id": "group-a"},
        {"id": "b", "organizer": "Same Name", "group_id": "group-b"},
    ]
    candidate = audit(events)["candidates"][0]
    assert candidate["decision"] == "distinct"
    assert candidate["evidence"] == ["vrchat-group:group-a", "vrchat-group:group-b"]


def test_display_name_only_is_ambiguous_and_unknown_urls_are_not_invented():
    candidate = audit([{"id": "a", "organizer": "Unknown"}])["candidates"][0]
    assert candidate["decision"] == "ambiguous"
    assert candidate["evidence"] == []


def test_result_does_not_depend_on_collection_order():
    events = [
        {"id": "z", "organizer": "B", "official_url": "https://b.example/events/1"},
        {"id": "a", "organizer": "A", "official_url": "https://a.example/events/1"},
    ]
    assert audit(events) == audit(list(reversed(events)))

def test_shared_event_platform_origin_is_not_organizer_identity():
    events = [
        {"id": "a", "organizer": "Shared Name", "official_url": "https://x.com/first"},
        {"id": "b", "organizer": "Shared Name", "official_url": "https://x.com/second"},
    ]
    candidate = audit(events)["candidates"][0]
    assert candidate["decision"] == "ambiguous"
    assert candidate["evidence"] == []


def test_distinct_organizer_profiles_on_same_host_do_not_merge():
    events = [
        {"id": "a", "organizer": "Shared Name", "organizer_url": "https://example.com/people/a"},
        {"id": "b", "organizer": "Shared Name", "organizer_url": "https://example.com/people/b"},
    ]
    assert audit(events)["candidates"][0]["decision"] == "distinct"


def test_identical_organizer_profile_merges_but_generic_or_credential_url_does_not():
    events = [
        {"id": "a", "organizer": "Shared Name", "organizer_url": "https://example.com/people/a"},
        {"id": "b", "organizer": "Shared Name", "organizer_url": "https://example.com/people/a/"},
    ]
    assert audit(events)["candidates"][0]["decision"] == "merged"
    events[1]["organizer_url"] = "https://user@example.com/people/a"
    assert audit(events)["candidates"][0]["decision"] == "ambiguous"
    events[1]["organizer_url"] = "https://example.com/"
    assert audit(events)["candidates"][0]["decision"] == "ambiguous"
