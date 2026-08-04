import json
from pathlib import Path

from cast_event_cal.ontology import enrich_event, select_entry, validate_ontology


ROOT = Path(__file__).resolve().parents[1]


def load_ontology() -> dict:
    return json.loads((ROOT / "config" / "event_ontology.json").read_text(encoding="utf-8"))


def test_series_ontology_is_human_curated_and_valid() -> None:
    ontology = load_ontology()
    validate_ontology(ontology)
    governance = ontology["governance"]
    assert governance["curation_mode"] == "human_only"
    assert governance["automatic_entry_creation"] is False
    assert governance["automatic_entry_rewrite"] is False
    assert governance["observed_events_may_only_link_to_existing_entries"] is True


def test_curated_entries_have_stable_profile_fields() -> None:
    ontology = load_ontology()
    assert ontology["schema_version"] == "2.0"
    for entry in ontology["entries"]:
        assert entry["schedule"]["type"] in {"recurring", "irregular", "one_off"}
        assert entry["schedule"]["label"]
        assert entry["schedule"]["cadence"]
        assert entry["introduction"]
        assert entry["highlights"]
        assert entry["first_time_guide"]
        assert entry["curation"]["status"] == "human_curated"
        assert entry["curation"]["reviewed_at"]
        assert all(url.startswith("https://") for url in entry["curation"]["sources"])


def test_matched_event_receives_series_profile_and_keeps_announcement_first() -> None:
    entry = load_ontology()["entries"][1]
    event = {
        "id": "example",
        "title": "Cafe & Bar FOR LIGHT 営業告知",
        "description": "本日の営業案内",
        "organizer": "@FOR_LIGHT202209",
        "url": "https://example.com/current-announcement",
        "tags": ["VRChat"],
    }
    enriched = enrich_event(event, entry)
    assert enriched["ontology_id"] == "cafe-bar-for-light"
    assert enriched["series_profile"]["schedule"]["type"] == "recurring"
    assert enriched["series_profile"]["introduction"] == entry["introduction"]
    assert enriched["series_profile"]["highlights"] == entry["highlights"]
    assert enriched["series_profile"]["first_time_guide"] == entry["first_time_guide"]
    assert enriched["official_links"][0]["kind"] == "announcement"
    assert enriched["official_links"][0]["url"] == event["url"]
    assert any(link["kind"] == "official_x" for link in enriched["official_links"])
    assert "定期開催" in enriched["tags"]


def test_verified_high_frequency_series_match_deterministically() -> None:
    entries = load_ontology()["entries"]
    cases = [
        ("ASMR集会 初心者説明会", "ASMR集会", "asmr-gathering"),
        ("EN-JP Language Exchange（日曜）", "EN-JP Language Exchange", "en-jp-language-exchange"),
        ("VRCごいた会", "VRCごいた会", "vrc-goita"),
        ("ゆるゲMEET定期開催日", "ゆるゲMEET", "yuruge-meet"),
        ("水曜Quest初心者の集い", "水曜Quest初心者の集い", "wednesday-quest-beginners"),
    ]
    expected_ids = {expected_id for _, _, expected_id in cases}
    assert expected_ids <= {entry["canonical_id"] for entry in entries}

    for title, organizer, expected_id in cases:
        entry, status, evidence = select_entry(
            {"title": title, "description": "", "organizer": organizer},
            entries,
        )
        assert status == "matched"
        assert entry is not None
        assert entry["canonical_id"] == expected_id
        assert "alias" in evidence


def test_second_verified_series_batch_matches_deterministically() -> None:
    entries = load_ontology()["entries"]
    entries_by_id = {entry["canonical_id"]: entry for entry in entries}
    cases = [
        ("EXPLOIT部 定期対戦会", "EXPLOIT", "exploit-club"),
        ("VRCゲームワールド部 月曜イベント", "VRCゲームワールド部", "vrc-game-world-club"),
        ("ML集会", "ML集会", "ml-gathering"),
        ("Personally match", "Personally match 開催通知", "personally-match"),
        ("VRC初心者ワールドツアー", "VRC初心者ワールドツアー", "vrc-beginner-world-tour"),
        ("VRCフィットボクシング集会（土曜）", "VRCフィットボクシング集会", "vrc-fit-boxing"),
        ("VRCフィットボクシング集会（日曜）", "VRCフィットボクシング集会", "vrc-fit-boxing"),
    ]
    expected_ids = {expected_id for _, _, expected_id in cases}
    assert expected_ids <= entries_by_id.keys()
    assert entries_by_id["vrc-fit-boxing"]["category"] == "wellness"
    assert entries_by_id["vrc-fit-boxing"]["subcategory"] == "fitness"

    for title, organizer, expected_id in cases:
        entry, status, evidence = select_entry(
            {"title": title, "description": "", "organizer": organizer},
            entries,
        )
        assert status == "matched"
        assert entry is not None
        assert entry["canonical_id"] == expected_id
        assert "alias" in evidence



def test_third_verified_series_batch_matches_deterministically() -> None:
    entries = load_ontology()["entries"]
    entries_by_id = {entry["canonical_id"]: entry for entry in entries}
    cases = [
        ("VRCでボーっとする会", "VRCでボーっとする会", "vrc-idle-gathering"),
        ("VRCふれあい動物園", "VRCふれあい動物園", "vrc-petting-zoo"),
    ]
    assert {expected_id for _, _, expected_id in cases} <= entries_by_id.keys()
    assert entries_by_id["vrc-idle-gathering"]["category"] == "wellness"
    assert entries_by_id["vrc-petting-zoo"]["category"] == "community"

    for title, organizer, expected_id in cases:
        entry, status, evidence = select_entry(
            {"title": title, "description": "", "organizer": organizer},
            entries,
        )
        assert status == "matched"
        assert entry is not None
        assert entry["canonical_id"] == expected_id
        assert "alias" in evidence
